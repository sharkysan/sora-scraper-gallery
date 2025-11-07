# Sora Gallery (Angular)

Displays images and prompt metadata scraped by the Python scraper.

## Prerequisites
- Node.js 18+
- npm

## Setup

```bash
cd web
npm install
npm run start
```

The app will open at http://localhost:4200 and read data from:
- `assets/downloads/summary.json`
- images in `assets/downloads/images/`

This mapping is configured in `angular.json` to point to `../downloads` at build/serve time. Make sure you have run the scraper so that `downloads/summary.json` and the images exist.

## Notes
- Use the search box to filter by prompt text.
- Use the limit selector to control how many items are rendered.

