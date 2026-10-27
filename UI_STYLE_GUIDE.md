# Signal Desk UI style guide

Signal Desk uses a small, consistent design system for the Django workspace and admin console. It takes cues from Google’s clear data hierarchy, Apple’s restrained spacing and surfaces, and NVIDIA’s confident green accent, while keeping its own brand and layouts.

## Design tokens

| Figma token | CSS variable | Light value | Purpose |
|---|---|---|---|
| `color/text/primary` | `--ink` | `#14211d` | Headings, key values |
| `color/text/secondary` | `--muted` | `#71817b` | Supporting text, timestamps |
| `color/surface/page` | `--paper` | `#f4f7f5` | App canvas |
| `color/surface/card` | `--surface` | `#ffffff` | Cards, forms, tables |
| `color/border/subtle` | `--line` | `#e4ebe7` | Dividers and outlines |
| `color/brand/primary` | `--green` | `#76b900` | Primary actions, chart series |
| `color/data/blue` | `--blue` | `#4285f4` | Secondary series and links |
| `color/data/yellow` | `--yellow` | `#f4b400` | Conversion and attention states |
| `radius/control` | `--radius-sm` | `10px` | Inputs, small controls |
| `radius/card` | `--radius` | `16px` | Cards and panels |
| `radius/feature` | `--radius-lg` | `22px` | Feature surfaces |
| `space/2`–`space/8` | `--space-2`–`--space-8` | `8px`–`32px` | Layout rhythm |
| `elevation/card` | `--shadow-card` | soft, layered shadow | Quiet separation from canvas |

Dark mode maps the same semantic tokens to dark surfaces and accessible contrast; users can switch themes from the top bar. Typography uses Inter when installed, then SF Pro, Segoe UI, and system fonts. No remote font or icon request is required.

## Components

- **Navigation:** persistent desktop sidebar, compact mobile drawer, active-page state, account controls.
- **Actions:** one strong green primary action, white secondary actions, clear disabled/focus states.
- **Metrics:** compact numeric cards with a single category icon and restrained color tint.
- **Charts:** labeled horizontal bar charts for segment mix and action progression; colors are repeated consistently and values remain visible.
- **Tables:** quiet headers, readable IDs, status chips, row hover, empty states, and horizontal scrolling on narrow screens.
- **Forms:** explicit labels, field-level error placement, clear helper text, and aligned cancel/save actions.
- **History:** vertical timeline for support and action events.
- **Admin:** matching Signal Desk header, custom sign-in surface, and coordinated controls while retaining Django’s admin workflows.

## Motion and accessibility

Page content enters with a short fade and lift; charts grow from the left; buttons and cards lift slightly on hover. `prefers-reduced-motion` disables those transitions. Icons are local inline SVG symbols with consistent stroke weight and accessible labels. Keyboard focus remains visible, and charts include text labels and values so color is never the only signal.

## Implementation

- Shared app styles: `segments/static/segments/app.css`
- Admin styles: `segments/static/segments/admin.css`
- Theme and responsive navigation: `segments/static/segments/app.js`
- Shared workspace layout: `templates/base.html`
