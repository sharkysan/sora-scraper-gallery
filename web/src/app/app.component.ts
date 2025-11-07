import { Component, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';

type SummaryItem = {
  id: number;
  prompt?: string;
  image_filename?: string;
  image_url?: string;
  timestamp?: string;
  detail_url?: string;
};

type Summary = {
  total_items: number;
  scrape_date: string;
  items: SummaryItem[];
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  readonly title = 'Sora Gallery';

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly items = signal<SummaryItem[]>([]);
  readonly query = signal('');
  readonly currentPage = signal(1);
  readonly itemsPerPage = signal(24);

  readonly filtered = computed(() => {
    const q = this.query().toLowerCase().trim();
    return q
      ? this.items().filter(i => (i.prompt || '').toLowerCase().includes(q))
      : this.items();
  });

  readonly paginated = computed(() => {
    const filtered = this.filtered();
    const page = this.currentPage();
    const perPage = this.itemsPerPage();
    const start = (page - 1) * perPage;
    const end = start + perPage;
    return filtered.slice(start, end);
  });

  readonly totalPages = computed(() => {
    const filtered = this.filtered();
    const perPage = this.itemsPerPage();
    return Math.ceil(filtered.length / perPage);
  });

  readonly pageInfo = computed(() => {
    const filtered = this.filtered();
    const page = this.currentPage();
    const perPage = this.itemsPerPage();
    const start = (page - 1) * perPage + 1;
    const end = Math.min(page * perPage, filtered.length);
    return { start, end, total: filtered.length };
  });

  constructor() {
    this.load();
  }

  onQueryInput(event: Event) {
    const target = event.target as HTMLInputElement;
    this.query.set(target.value);
    this.currentPage.set(1); // Reset to first page on search
  }

  onItemsPerPageChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    this.itemsPerPage.set(+target.value);
    this.currentPage.set(1); // Reset to first page
  }

  goToPage(page: number) {
    const total = this.totalPages();
    if (page >= 1 && page <= total) {
      this.currentPage.set(page);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  previousPage() {
    const current = this.currentPage();
    if (current > 1) {
      this.goToPage(current - 1);
    }
  }

  nextPage() {
    const current = this.currentPage();
    const total = this.totalPages();
    if (current < total) {
      this.goToPage(current + 1);
    }
  }

  getPageNumbers(): number[] {
    const current = this.currentPage();
    const total = this.totalPages();
    const pages: number[] = [];
    
    // Show max 7 page numbers
    let start = Math.max(1, current - 3);
    let end = Math.min(total, current + 3);
    
    // Adjust if we're near the start or end
    if (end - start < 6) {
      if (start === 1) {
        end = Math.min(total, 7);
      } else if (end === total) {
        start = Math.max(1, total - 6);
      }
    }
    
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }
    
    return pages;
  }

  private async load() {
    this.loading.set(true);
    this.error.set(null);
    try {
      // summary.json is exposed via assets mapping to ../downloads
      const res = await fetch('assets/downloads/summary.json', { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const summary: Summary = await res.json();

      // Normalize items; build image path preferring saved filename
      const mapped = (summary.items || []).map((it) => {
        const imagePath = it.image_filename
          ? `assets/downloads/images/${it.image_filename}`
          : undefined;
        return { ...it, image_filename: it.image_filename, image_url: imagePath ?? it.image_url } as SummaryItem;
      }).filter(i => !!(i.image_filename || i.image_url));

      this.items.set(mapped);
    } catch (e: any) {
      this.error.set(e?.message ?? 'Failed to load summary');
    } finally {
      this.loading.set(false);
    }
  }
}


