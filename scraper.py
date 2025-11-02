"""
Sora Library Scraper
Downloads images and prompts from https://sora.chatgpt.com/library
"""

import os
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class SoraScraper:
    def __init__(self, output_dir="downloads", use_persistent_context=False, browser_data_dir=None, max_items=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.images_dir = self.output_dir / "images"
        self.prompts_dir = self.output_dir / "prompts"
        self.images_dir.mkdir(exist_ok=True)
        self.prompts_dir.mkdir(exist_ok=True)
        
        self.items = []
        self.use_persistent_context = use_persistent_context
        self.browser_data_dir = browser_data_dir or (self.output_dir / "browser_data")
        self.max_items = max_items  # Maximum number of items to process (None = all)
        
    def wait_for_login_page(self, page, timeout=60):
        """Wait for login page to be visible"""
        print("Waiting for login page to appear...")
        print(f"Current URL: {page.url}")
        
        # Wait for page to load - OpenAI uses React, so we need to wait for JS to load
        print("Waiting for JavaScript to load...")
        try:
            # Wait for any content to appear
            page.wait_for_load_state('networkidle', timeout=30000)
            time.sleep(2)  # Extra wait for React to render
        except:
            print("⚠ Network idle timeout, but continuing...")
            time.sleep(3)  # Give it more time
        
        # OpenAI auth page specific selectors
        openai_login_selectors = [
            'button:has-text("Continue")',
            'button:has-text("Log in")',
            'button:has-text("Sign in")',
            'button[type="submit"]',
            'input[type="email"]',
            'input[type="text"]',
            'input[autocomplete="username"]',
            'input[name="email"]',
            'input[placeholder*="email" i]',
            '[data-testid*="email"]',
            '[data-testid*="username"]',
            'form',
            'div[role="main"]',
            'main',
        ]
        
        print("Looking for login elements...")
        for selector in openai_login_selectors:
            try:
                element = page.wait_for_selector(selector, timeout=5000, state='visible')
                if element:
                    # Check if element is actually visible and has content
                    bounding_box = element.bounding_box()
                    if bounding_box and (bounding_box['width'] > 0 and bounding_box['height'] > 0):
                        print(f"✓ Login page detected (found: {selector})")
                        return True
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                print(f"  Error checking {selector}: {e}")
                continue
        
        # Check page content - if there's actual text content, page loaded
        try:
            body_text = page.evaluate('document.body.innerText || document.body.textContent || ""')
            if body_text and len(body_text.strip()) > 50:  # Reasonable amount of content
                print("✓ Page has content, login page should be visible")
                return True
        except:
            pass
        
        # If no login elements found, check if we're already logged in
        if 'library' in page.url.lower():
            print("Already on library page - might be logged in!")
            return True
        
        print("⚠ Could not find login elements. Taking screenshot for debugging...")
        screenshot_path = self.output_dir / "login_debug.png"
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")
        except Exception as e:
            print(f"Could not save screenshot: {e}")
        
        # Save page content for debugging
        try:
            html_file = self.output_dir / "login_debug.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(page.content())
            print(f"Page HTML saved to: {html_file}")
        except Exception as e:
            print(f"Could not save HTML: {e}")
        
        print(f"Current URL: {page.url}")
        print("⚠️  If the page appears empty, try:")
        print("   1. Manually refresh the page in the browser (F5)")
        print("   2. Wait a few more seconds for the page to load")
        print("   3. Check the screenshot at: " + str(screenshot_path))
        return False
    
    def wait_for_login(self, page, timeout=300):
        """Wait for user to manually log in"""
        print("\n" + "="*60)
        print("WAITING FOR LOGIN")
        print("="*60)
        print("Please log in to ChatGPT/Sora in the browser window.")
        print("The scraper will wait for you to complete the login process.")
        print("="*60 + "\n")
        
        # Make sure browser is visible and bring to front
        page.bring_to_front()
        time.sleep(1)
        
        # Wait for login page elements to appear first
        print("\nChecking if login page is loaded...")
        page_loaded = self.wait_for_login_page(page, timeout=45)
        
        if not page_loaded:
            print("\n⚠ Login page elements not found immediately.")
            print("The page might still be loading, or you might need to refresh it.")
            print("The script will continue waiting - you can manually refresh the page if needed.")
            print("\nTIP: If the page is empty, try:")
            print("   - Press F5 to refresh the page")
            print("   - Wait a few more seconds")
            print("   - Check the browser console for errors\n")
        else:
            print("✓ Login page appears to be loaded!\n")
        
        # Wait for navigation to library page (indicating successful login)
        print("\nWaiting for successful login...")
        print("Once you log in, the page should navigate to the library.")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_url = page.url
            print(f"Current URL: {current_url}")
            # Check if we're on the library page
            if 'library' in current_url.lower():
                print("✓ Login successful! Redirected to library page.")
                time.sleep(2)  # Wait for page to fully load
                return True
            
            # Check if login page is still visible (user hasn't logged in yet)
            try:
                # Look for any sign that we're still on login/auth page
                if 'login' in current_url.lower() or 'auth' in current_url.lower():
                    time.sleep(2)  # Wait a bit before checking again
                    continue
            except:
                pass
            
            time.sleep(2)  # Check every 2 seconds
        
        print("⚠ Timeout waiting for login. Please try again.")
        return False
    
    def extract_links_from_page(self, page):
        """Extract detail page links from current page state"""
        detail_links = []
        
        # Try multiple selectors to find clickable library items (links to detail pages)
        # Detail pages have pattern "g/gen" in the URL
        selectors = [
            'a[href*="/g/gen"]',
            'a[href*="g/gen"]',
            'a[href*="/library/"]',
            'a[href*="/detail"]',
            'article a',
            '[data-testid*="library"] a',
            '[data-testid*="card"] a',
            '.library-item a',
            'div[role="article"] a',
        ]
        
        elements = None
        
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    break
            except:
                continue
        
        if not elements or len(elements) == 0:
            return detail_links
        
        # Extract detail page URLs from clickable elements
        for idx, element in enumerate(elements):
            try:
                href = element.get_attribute('href')
                if href:
                    # Handle relative URLs
                    if href.startswith('/'):
                        href = 'https://sora.chatgpt.com' + href
                    elif not href.startswith('http'):
                        href = 'https://sora.chatgpt.com' + '/' + href.lstrip('/')
                    
                    # Include links that match the "g/gen" pattern or other detail page patterns
                    if '/g/gen' in href or 'g/gen' in href or '/library/' in href or '/detail' in href:
                        # Normalize URL (remove trailing slashes, fragments, etc.)
                        normalized_url = href.split('#')[0].split('?')[0].rstrip('/')
                        detail_links.append({
                            'detail_url': normalized_url,
                            'original_url': href,
                            'element': element
                        })
            except Exception as e:
                continue
        
        return detail_links
    
    def scroll_and_load_more(self, page, collected_links=None):
        """Scroll down to load more items and collect links during scrolling"""
        if collected_links is None:
            collected_links = set()
        
        # Check if we have a limit
        has_limit = self.max_items is not None and self.max_items > 0
        limit_reached = False
        
        if has_limit:
            print(f"Scrolling to load items and collecting links (limit: {self.max_items})...")
        else:
            print("Scrolling to load more items and collecting links...")
        
        last_height = page.evaluate("document.body.scrollHeight")
        scroll_count = 0
        last_link_count = 0
        
        while True:
            scroll_count += 1
            
            # Extract links from current page state before scrolling
            current_links = self.extract_links_from_page(page)
            for link_data in current_links:
                collected_links.add(link_data['detail_url'])
            
            new_link_count = len(collected_links)
            if new_link_count > last_link_count:
                print(f"  Found {new_link_count} unique links so far...")
                last_link_count = new_link_count
            
            # Check if limit reached before scrolling
            if has_limit and len(collected_links) >= self.max_items:
                limit_reached = True
                print(f"  ✓ Limit reached ({self.max_items} links). Stopping scroll...")
                break
            
            # Scroll down
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)  # Wait for content to load
            
            # Extract links again after scrolling (in case new items loaded)
            current_links = self.extract_links_from_page(page)
            for link_data in current_links:
                collected_links.add(link_data['detail_url'])
            
            new_link_count = len(collected_links)
            if new_link_count > last_link_count:
                print(f"  Found {new_link_count} unique links so far...")
                last_link_count = new_link_count
            
            # Check if limit reached after scrolling
            if has_limit and len(collected_links) >= self.max_items:
                limit_reached = True
                print(f"  ✓ Limit reached ({self.max_items} links). Stopping scroll...")
                break
            
            # Check if new content loaded
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                # No new content, but wait a bit more and check again
                time.sleep(1)
                final_height = page.evaluate("document.body.scrollHeight")
                if final_height == new_height:
                    # Try extracting links one more time
                    current_links = self.extract_links_from_page(page)
                    for link_data in current_links:
                        collected_links.add(link_data['detail_url'])
                    
                    # Check limit one more time
                    if has_limit and len(collected_links) >= self.max_items:
                        limit_reached = True
                        print(f"  ✓ Limit reached ({self.max_items} links). Stopping scroll...")
                    
                    if not limit_reached:
                        break
                elif has_limit and len(collected_links) >= self.max_items:
                    limit_reached = True
                    print(f"  ✓ Limit reached ({self.max_items} links). Stopping scroll...")
                    break
            last_height = new_height
            
            # Stop if limit reached
            if limit_reached:
                break
            
            # Check for "Load more" button and click if present
            try:
                load_more_button = page.query_selector('button:has-text("Load more"), button:has-text("Show more")')
                if load_more_button and load_more_button.is_visible():
                    load_more_button.click()
                    time.sleep(2)
                    # Extract links after clicking load more
                    current_links = self.extract_links_from_page(page)
                    for link_data in current_links:
                        collected_links.add(link_data['detail_url'])
                    
                    # Check limit after clicking load more
                    if has_limit and len(collected_links) >= self.max_items:
                        limit_reached = True
                        print(f"  ✓ Limit reached ({self.max_items} links). Stopping scroll...")
                        break
            except:
                pass
        
        # Final extraction only if limit not reached (to make sure we got everything if no limit)
        if not limit_reached:
            print("  Final link extraction...")
            final_links = self.extract_links_from_page(page)
            for link_data in final_links:
                collected_links.add(link_data['detail_url'])
        
        final_count = len(collected_links)
        if has_limit:
            print(f"  Total unique links collected: {final_count} (limit: {self.max_items})")
        else:
            print(f"  Total unique links collected: {final_count}")
        
        return collected_links
    
    def extract_items(self, page):
        """Extract all clickable items/links from the library page during scrolling"""
        print("Extracting items from the library...")
        
        # Wait for content to load
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # Scroll and collect links during scrolling
        collected_link_urls = self.scroll_and_load_more(page)
        
        if not collected_link_urls or len(collected_link_urls) == 0:
            print("Warning: Could not find clickable library items.")
            print("Saving page for debugging...")
            html_file = self.output_dir / "page_debug.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(page.content())
            return []
        
        # Convert collected URLs to link objects
        unique_links = []
        for idx, url in enumerate(sorted(collected_link_urls)):
            unique_links.append({
                'id': idx,
                'detail_url': url,
                'element': None  # We don't need the element anymore
            })
        
        print(f"\n✓ Collected {len(unique_links)} unique detail page links during scrolling")
        print(f"  Now processing each detail page...\n")
        return unique_links
    
    def process_item_detail(self, page, context, item_link, idx, total):
        """Navigate to detail page, extract prompt from button, and download image"""
        item_data = {
            'id': item_link['id'],
            'detail_url': item_link['detail_url'],
            'prompt': '',
            'image_filename': '',
            'timestamp': time.strftime('%Y%m%d_%H%M%S')
        }
        
        try:
            print(f"\n[{idx}/{total}] Processing item {idx}...")
            print(f"  URL: {item_link['detail_url']}")
            
            # Navigate to detail page
            page.goto(item_link['detail_url'], wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)  # Wait for page to load
            page.wait_for_load_state('networkidle', timeout=15000)
            time.sleep(1)
            
            # Try to find prompt - look for button tag after the prompt text
            # First find the prompt text element
            prompt_text = None
            prompt_selectors = [
                'p[class*="prompt"]',
                'div[class*="prompt"]',
                'div[class*="text"]',
                'p',
                'span[class*="prompt"]',
                '[data-testid*="prompt"]',
            ]
            
            for selector in prompt_selectors:
                try:
                    prompt_elem = page.query_selector(selector)
                    if prompt_elem:
                        text = prompt_elem.inner_text().strip()
                        if text and len(text) > 10:
                            prompt_text = text
                            # Try to find button after this element
                            # Look for next sibling button or button in parent
                            try:
                                # Try to find button after the prompt element
                                button_text = prompt_elem.evaluate('''
                                    (element) => {
                                        let current = element.nextElementSibling;
                                        while (current) {
                                            if (current.tagName === 'BUTTON') {
                                                return current.innerText || current.textContent || '';
                                            }
                                            current = current.nextElementSibling;
                                        }
                                        // Try parent's next sibling
                                        if (element.parentElement) {
                                            current = element.parentElement.nextElementSibling;
                                            while (current) {
                                                if (current.tagName === 'BUTTON') {
                                                    return current.innerText || current.textContent || '';
                                                }
                                                current = current.nextElementSibling;
                                            }
                                        }
                                        return null;
                                    }
                                ''')
                                if button_text and len(button_text) > len(text):
                                    prompt_text = button_text.strip()
                            except:
                                pass
                            break
                except:
                    continue
            
            # Also try to find button directly with prompt-related text
            if not prompt_text or len(prompt_text) < 20:
                button_selectors = [
                    'button:has-text("prompt")',
                    'button[aria-label*="prompt" i]',
                    'button[data-testid*="prompt"]',
                    'button',
                ]
                
                for selector in button_selectors:
                    try:
                        buttons = page.query_selector_all(selector)
                        for button in buttons:
                            button_text = button.inner_text().strip()
                            # Look for buttons with longer text that might be the prompt
                            if button_text and len(button_text) > 20 and len(button_text) < 2000:
                                # Check if it looks like a prompt (contains descriptive text)
                                if not button_text.lower().startswith(('click', 'download', 'save', 'share', 'copy')):
                                    prompt_text = button_text
                                    break
                        if prompt_text:
                            break
                    except:
                        continue
            
            # If still no prompt, try getting all text on page
            if not prompt_text or len(prompt_text) < 10:
                try:
                    body_text = page.evaluate('document.body.innerText || document.body.textContent || ""')
                    # Extract the longest paragraph-like text that might be the prompt
                    lines = [line.strip() for line in body_text.split('\n') if line.strip()]
                    for line in sorted(lines, key=len, reverse=True):
                        if len(line) > 20 and len(line) < 2000:
                            if not any(skip in line.lower() for skip in ['menu', 'navigation', 'header', 'footer', 'cookie']):
                                prompt_text = line
                                break
                except:
                    pass
            
            if prompt_text:
                item_data['prompt'] = prompt_text
                print(f"  ✓ Found prompt ({len(prompt_text)} chars)")
            else:
                print(f"  ⚠ Could not find prompt text")
            
            # Download image directly from detail page (no button click)
            # Look for img tag with alt="Generated image" which contains the main WebP image
            print(f"  → Looking for image to download directly...")
            download_clicked = False
            
            try:
                # First, try to find the specific img tag with alt="Generated image"
                img = None
                
                # Priority 1: Look for img with alt="Generated image" (exact match)
                try:
                    # Try exact match first
                    img_candidates = page.query_selector_all('img[alt="Generated image"]')
                    if not img_candidates:
                        # Try case-insensitive match
                        all_imgs = page.query_selector_all('img')
                        for candidate in all_imgs:
                            try:
                                alt_text = candidate.get_attribute('alt')
                                if alt_text and 'Generated image' in alt_text:
                                    img_candidates.append(candidate)
                            except:
                                pass
                    
                    if img_candidates:
                        print(f"  ✓ Found {len(img_candidates)} image(s) with alt='Generated image'")
                        # Get the first one (should be the main generated image)
                        img = img_candidates[0]
                        print(f"  → Using image with alt='Generated image'")
                except Exception as e:
                    print(f"  ⚠ Error finding img with alt='Generated image': {e}")
                    pass
                
                # Priority 3: Find largest WebP image
                if not img:
                    try:
                        all_imgs = page.query_selector_all('img')
                        if all_imgs:
                            # Find the largest WebP image
                            largest_webp = None
                            largest_webp_size = 0
                            largest_img = None
                            largest_size = 0
                            
                            for candidate_img in all_imgs:
                                try:
                                    if candidate_img.is_visible():
                                        box = candidate_img.bounding_box()
                                        if box and box['width'] > 0 and box['height'] > 0:
                                            size = box['width'] * box['height']
                                            img_src_check = candidate_img.get_attribute('src') or candidate_img.get_attribute('data-src') or ''
                                            
                                            # Prioritize WebP images
                                            if '.webp' in img_src_check.lower() and size > largest_webp_size:
                                                largest_webp_size = size
                                                largest_webp = candidate_img
                                            elif size > largest_size:
                                                largest_size = size
                                                largest_img = candidate_img
                                except:
                                    continue
                            
                            # Prefer largest WebP, fallback to largest image
                            img = largest_webp if largest_webp else largest_img
                            if img:
                                if largest_webp:
                                    print(f"  → Using largest WebP image ({largest_webp_size}px)")
                                else:
                                    print(f"  → Using largest image ({largest_size}px)")
                    except:
                        pass
                
                if img:
                    # Try to get image URL from various attributes
                    img_src = None
                    src_attributes = ['src', 'data-src', 'data-url', 'data-original', 'data-lazy-src']
                    
                    for attr in src_attributes:
                        try:
                            img_src = img.get_attribute(attr)
                            if img_src and img_src.strip():
                                break
                        except:
                            continue
                    
                    # If no src found, try to get from srcset (prefer largest WebP)
                    if not img_src:
                        try:
                            srcset = img.get_attribute('srcset')
                            if srcset:
                                # Parse srcset and prefer largest WebP if available
                                srcset_parts = srcset.split(',')
                                webp_urls = []
                                largest_webp_url = None
                                largest_webp_width = 0
                                
                                for part in srcset_parts:
                                    part = part.strip()
                                    parts = part.split()
                                    url_part = parts[0] if len(parts) > 0 else part
                                    # Try to get width descriptor
                                    width = 0
                                    if len(parts) > 1:
                                        width_str = parts[1]
                                        if width_str.endswith('w'):
                                            try:
                                                width = int(width_str[:-1])
                                            except:
                                                pass
                                    
                                    # Collect WebP URLs with their sizes
                                    if '.webp' in url_part.lower():
                                        if width > largest_webp_width:
                                            largest_webp_width = width
                                            largest_webp_url = url_part
                                        webp_urls.append((url_part, width))
                                
                                # Use largest WebP URL, or first WebP, or last URL as fallback
                                if largest_webp_url:
                                    img_src = largest_webp_url
                                    print(f"  → Found largest WebP in srcset ({largest_webp_width}w)")
                                elif webp_urls:
                                    # Sort by width and get largest
                                    webp_urls.sort(key=lambda x: x[1], reverse=True)
                                    img_src = webp_urls[0][0]
                                    print(f"  → Found WebP in srcset")
                                else:
                                    # Fallback: get last URL from srcset
                                    if srcset_parts:
                                        img_src = srcset_parts[-1].strip().split()[0]
                        except:
                            pass
                    
                    if img_src:
                        # Handle relative URLs
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src
                        elif img_src.startswith('/'):
                            img_src = 'https://sora.chatgpt.com' + img_src
                        elif not img_src.startswith('http'):
                            img_src = 'https://sora.chatgpt.com' + '/' + img_src.lstrip('/')
                        
                        print(f"  ✓ Found image URL: {img_src[:80]}...")
                        
                        filename_base = f"item_{item_data['id']:04d}_{item_data['timestamp']}"
                        
                        # Determine file extension from URL (prefer WebP if detected)
                        ext = '.jpg'
                        img_src_lower = img_src.lower()
                        if '.webp' in img_src_lower:
                            ext = '.webp'
                        elif '.png' in img_src_lower:
                            ext = '.png'
                        elif '.gif' in img_src_lower:
                            ext = '.gif'
                        
                        img_filename = f"{filename_base}{ext}"
                        
                        if self.download_image(img_src, img_filename):
                            item_data['image_filename'] = img_filename
                            print(f"  ✓ Downloaded image directly: {img_filename}")
                            download_clicked = True
                        else:
                            print(f"  ❌ Failed to download image from URL: {img_src}")
                    else:
                        print(f"  ⚠ Could not extract image URL from img element")
                else:
                    print(f"  ⚠ Could not find image on page")
                        
            except Exception as e2:
                print(f"  ❌ Error downloading image: {e2}")
                import traceback
                traceback.print_exc()
            
            # Save prompt to JSON file
            if item_data['prompt']:
                prompt_filename = f"item_{item_data['id']:04d}_{item_data['timestamp']}.json"
                if self.save_prompt(item_data, prompt_filename):
                    print(f"  ✓ Saved prompt: {prompt_filename}")
            
            return item_data
            
        except Exception as e:
            print(f"  ❌ Error processing item {idx}: {e}")
            import traceback
            traceback.print_exc()
            return item_data
    
    def download_image(self, url, filename):
        """Download an image from URL (supports WebP and other formats)"""
        if not url:
            return False
        
        try:
            import urllib.request
            from urllib.parse import urlparse
            
            filepath = self.images_dir / filename
            
            # Add headers to mimic browser request, accept WebP
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://sora.chatgpt.com/',
            })
            
            with urllib.request.urlopen(req) as response:
                with open(filepath, 'wb') as out_file:
                    out_file.write(response.read())
            
            return True
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return False
    
    def save_prompt(self, item_data, filename):
        """Save prompt to text file"""
        try:
            filepath = self.prompts_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(item_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving prompt {filename}: {e}")
            return False
    
    def add_stealth_script(self, page):
        """Add comprehensive scripts to make browser undetectable from Google and other detection systems"""
        # Comprehensive stealth script to hide automation
        page.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override webdriver property completely
            delete Object.getPrototypeOf(navigator).webdriver;
            
            // Add Chrome object with runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Override plugins with realistic values
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [];
                    for (let i = 0; i < 5; i++) {
                        plugins.push({
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        });
                    }
                    return plugins;
                }
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Override permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Add realistic platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // Override userAgent to match real Chrome
            const originalUserAgent = navigator.userAgent;
            Object.defineProperty(navigator, 'userAgent', {
                get: () => originalUserAgent
            });
            
            // Hide automation indicators
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: window.navigator.permissions.query.bind(window.navigator.permissions)
                })
            });
            
            // Override Notification permission
            Object.defineProperty(Notification, 'permission', {
                get: () => 'default'
            });
            
            // Remove automation indicators from window
            if (window.document && window.document.documentElement) {
                Object.defineProperty(window.document.documentElement, 'webdriver', {
                    get: () => undefined
                });
            }
        """)
    
    def scrape(self):
        """Main scraping function"""
        with sync_playwright() as p:
            # Browser launch args with enhanced stealth settings
            # Removed flags that might trigger detection, added stealth-specific ones
            launch_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--window-size=1920,1080',
                '--start-maximized',
                '--disable-infobars',
                '--exclude-switches=enable-automation',
                '--disable-extensions',
                '--disable-notifications',
                '--disable-translate',
                '--mute-audio',
                '--force-color-profile=srgb',
            ]
            
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'locale': 'en-US',
                'timezone_id': 'America/New_York',
                'permissions': ['geolocation', 'notifications'],
                # Removed all extra_http_headers to avoid CORS issues with OpenAI CDN
                # Playwright's browser will automatically send appropriate headers
            }
            
            browser = None  # Initialize for cleanup
            
            if self.use_persistent_context:
                # Use persistent browser context (saves cookies and session)
                print("Using persistent browser context...")
                print(f"Browser data will be saved to: {self.browser_data_dir}")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.browser_data_dir),
                    headless=False,
                    args=launch_args,
                    **context_options
                )
                page = context.pages[0] if context.pages else context.new_page()
            else:
                # Launch browser with stealth settings
                browser = p.chromium.launch(
                    headless=False,
                    args=launch_args
                )
                
                # Create context with realistic settings
                context = browser.new_context(**context_options)
                page = context.new_page()
            
            # Add stealth scripts to make browser undetectable
            self.add_stealth_script(page)
            
            # Maximize window and bring to front
            page.set_viewport_size({'width': 1920, 'height': 1080})
            page.bring_to_front()
            time.sleep(1)
            
            try:
                # Navigate to library with realistic timing
                print("Navigating to Sora library...")
                
                # First visit a neutral page to build browser history
                print("1. Visiting neutral page first...")
                page.goto('https://www.google.com', wait_until='networkidle')
                time.sleep(2)
                
                # Now navigate to library
                print("2. Navigating to Sora library...")
                try:
                    # Use load state instead of domcontentloaded for better compatibility
                    page.goto('https://sora.chatgpt.com/library', wait_until='load', timeout=60000)
                    # Wait extra time for JavaScript to render
                    time.sleep(5)
                    # Wait for network to be idle
                    try:
                        page.wait_for_load_state('networkidle', timeout=15000)
                    except:
                        print("  Network idle timeout, but continuing...")
                except Exception as e:
                    print(f"  Navigation error: {e}")
                    print("  Continuing anyway...")
                    time.sleep(3)
                
                # Check current URL and page state
                current_url = page.url
                print(f"Current URL: {current_url}")
                
                # Bring browser to front to make sure it's visible
                page.bring_to_front()
                time.sleep(1)
                
                # Add some human-like mouse movement
                page.mouse.move(100, 100)
                time.sleep(0.5)
                page.mouse.move(200, 200)
                time.sleep(0.5)
                
                # Check if we need to log in
                needs_login = False
                
                # Check URL for login/auth indicators
                if any(keyword in current_url.lower() for keyword in ['login', 'auth', 'signin']):
                    needs_login = True
                    print("⚠ Login URL detected")
                
                # Check page content for login indicators
                try:
                    page_content = page.content().lower()
                    if any(keyword in page_content for keyword in ['sign in', 'log in', 'login', 'authenticate']):
                        # But check if we're actually on the library page (might just mention login in footer)
                        if 'library' not in current_url.lower():
                            needs_login = True
                            print("⚠ Login page content detected")
                except:
                    pass
                
                # Try to find library-specific elements
                try:
                    # Wait a bit for page to load
                    time.sleep(2)
                    library_elements = page.query_selector_all('[data-testid*="library"], article, [href*="/library/"]')
                    if not library_elements:
                        needs_login = True
                        print("⚠ Library content not found - might need login")
                except:
                    needs_login = True
                
                # If we need login, handle it
                if needs_login or 'library' not in current_url.lower():
                    print("\n" + "="*60)
                    print("LOGIN REQUIRED")
                    print("="*60)
                    print("The browser window should now be visible.")
                    print("Current URL:", page.url)
                    
                    # If on auth.openai.com and page is empty, wait for it to load
                    if 'auth.openai.com' in page.url.lower():
                        print("\n⚠ Detected OpenAI auth page. Waiting for page to load...")
                        print("If the page appears empty:")
                        print("  1. Wait 5-10 seconds for it to load")
                        print("  2. Or press F5 to refresh the page")
                        print("  3. The script will continue waiting...")
                        time.sleep(5)  # Give it time to load
                    
                    print("\nPlease log in to ChatGPT/Sora in the browser.")
                    print("="*60 + "\n")
                    
                    if not self.wait_for_login(page):
                        print("\n❌ Login not completed. Exiting...")
                        return
                
                # Make sure we're on the library page
                if 'library' not in page.url.lower():
                    print("\nNavigating to library page...")
                    page.goto('https://sora.chatgpt.com/library', wait_until='domcontentloaded')
                    time.sleep(3)
                
                # Final check - bring browser to front
                page.bring_to_front()
                print(f"\n✓ Current URL: {page.url}")
                print("✓ Ready to scrape library content\n")
                
                # Extract item links from library page
                item_links = self.extract_items(page)
                
                if not item_links:
                    print("No items found. The page structure might have changed.")
                    print("Please check the selectors in the code or inspect the page manually.")
                    
                    # Save page HTML for debugging
                    html_file = self.output_dir / "page_debug.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    print(f"Page HTML saved to {html_file} for debugging.")
                else:
                    # Limit items if max_items is set
                    total_items = len(item_links)
                    if self.max_items is not None and self.max_items > 0:
                        item_links = item_links[:self.max_items]
                        print(f"\nFound {total_items} items. Processing first {len(item_links)} items (limit: {self.max_items})...")
                    else:
                        print(f"\nFound {total_items} items. Processing all items...")
                    print("="*60)
                    
                    processed_items = []
                    
                    # Process each item: go to detail page, extract prompt, download image
                    for idx, item_link in enumerate(item_links, 1):
                        item_data = self.process_item_detail(page, context, item_link, idx, len(item_links))
                        processed_items.append(item_data)
                        
                        # Small delay between items
                        if idx < len(item_links):
                            time.sleep(1)
                    
                    # Save summary
                    summary = {
                        'total_items': len(processed_items),
                        'scrape_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'items': processed_items
                    }
                    
                    summary_file = self.output_dir / "summary.json"
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        json.dump(summary, f, indent=2, ensure_ascii=False)
                    
                    print("\n" + "="*60)
                    print(f"✓ Scraping complete!")
                    print("="*60)
                    print(f"  Total items processed: {len(processed_items)}")
                    print(f"  Items with prompts: {sum(1 for item in processed_items if item.get('prompt'))}")
                    print(f"  Items with images: {sum(1 for item in processed_items if item.get('image_filename'))}")
                    print(f"  Images saved to: {self.images_dir}")
                    print(f"  Prompts saved to: {self.prompts_dir}")
                    print(f"  Summary saved to: {summary_file}")
            
            except Exception as e:
                print(f"Error during scraping: {e}")
                import traceback
                traceback.print_exc()
            
            finally:
                # Keep browser open for a bit so user can see results
                print("\nClosing browser in 5 seconds...")
                time.sleep(5)
                if self.use_persistent_context:
                    context.close()
                else:
                    browser.close()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape images and prompts from Sora library')
    parser.add_argument('--output', '-o', default='downloads', 
                       help='Output directory (default: downloads)')
    parser.add_argument('--persistent', '-p', action='store_true',
                       help='Use persistent browser context (saves login session)')
    parser.add_argument('--browser-data', '-b', default=None,
                       help='Directory for browser data (default: output_dir/browser_data)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='Maximum number of images to process (default: all)')
    
    args = parser.parse_args()
    
    scraper = SoraScraper(
        output_dir=args.output,
        use_persistent_context=args.persistent,
        browser_data_dir=args.browser_data,
        max_items=args.limit
    )
    scraper.scrape()


if __name__ == '__main__':
    main()

