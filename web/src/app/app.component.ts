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
  readonly limit = signal(50);

  readonly filtered = computed(() => {
    const q = this.query().toLowerCase().trim();
    const base = q
      ? this.items().filter(i => (i.prompt || '').toLowerCase().includes(q))
      : this.items();
    return base.slice(0, this.limit());
  });

  constructor() {
    this.load();
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


