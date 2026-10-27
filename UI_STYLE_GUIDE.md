# Customer Signals UI style guide

Customer Signals uses a restrained operations interface: clear hierarchy, neutral surfaces, one muted green accent, and compact data views. The system avoids decorative logos, novelty marks, gradients, and nonessential motion.

## Design tokens

| Figma token | CSS variable | Light value | Purpose |
|---|---|---|---|
| `color/text/primary` | `--ink` | `#1c2923` | Headings, key values |
| `color/text/secondary` | `--muted` | `#718078` | Supporting text, timestamps |
| `color/surface/page` | `--paper` | `#f5f7f6` | App canvas |
| `color/surface/card` | `--surface` | `#ffffff` | Cards, forms, tables |
| `color/border/subtle` | `--line` | `#e3e8e5` | Dividers and outlines |
| `color/brand/primary` | `--green` | `#2f6b4f` | Primary actions, chart series |
| `color/data/blue` | `--blue` | `#5279a5` | Links and secondary status |
| `color/data/yellow` | `--yellow` | `#98712e` | Conversion and attention states |
| `radius/control` | `--radius-sm` | `10px` | Inputs, small controls |
| `radius/card` | `--radius` | `16px` | Cards and panels |
| `radius/feature` | `--radius-lg` | `22px` | Feature surfaces |
| `space/2`–`space/8` | `--space-2`–`--space-8` | `8px`–`32px` | Layout rhythm |
| `elevation/card` | `--shadow-card` | soft, layered shadow | Quiet separation from canvas |

Dark mode maps the same semantic tokens to dark surfaces; the same labeled switch and saved preference are shared by the workspace and admin header. Typography uses Inter when installed, then SF Pro, Segoe UI, and system fonts. No remote font or icon request is required.

## Components

- **Navigation:** persistent desktop sidebar, compact mobile drawer, active-page state, account controls, and a text-only wordmark.
- **Actions:** one muted-green primary action, white secondary actions, clear focus states.
- **Metrics:** compact numeric cards with restrained outline icons and no decorative color treatments.
- **Charts:** labeled horizontal bar charts for segment mix and action progression; one consistent series color and visible values.
- **Tables:** quiet headers, readable IDs, status chips, row hover, empty states, and horizontal scrolling on narrow screens.
- **Forms:** explicit labels, field-level error placement, clear helper text, and aligned cancel/save actions.
- **History:** vertical timeline for support and action events.
- **Admin:** matching Customer Signals header, a simple sign-in surface, and coordinated controls while retaining Django’s admin workflows.

## Motion and accessibility

Only chart bars animate briefly when first shown. Hover states use subtle color changes without lifting or scaling cards. `prefers-reduced-motion` disables transitions. Functional icons are simple line symbols with accessible labels; there is no decorative SVG logo. Keyboard focus remains visible, and charts include labels and values so color is never the only signal.

## Implementation

- Shared app styles: `segments/static/segments/app.css`
- Admin styles: `segments/static/segments/admin.css`
- Theme and responsive navigation: `segments/static/segments/app.js`
- Shared workspace layout: `templates/base.html`
