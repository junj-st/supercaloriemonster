# Frontend Styling Guide — Calorie Tracker

The visual language for the app: a calm, flat, hairline-bordered structure for anything you scan repeatedly (log lists, headers, navigation), paired with soft tinted "pills" for the three numbers you check most often — protein, carbs, fat — so those specific values pop without the rest of the UI feeling loud. Dark-mode-first, since this gets used at meals, often in the evening.

## 1. Design principles

1. **Numbers are the content.** Everything else — cards, borders, spacing — exists to frame the numbers, not compete with them. No decoration that isn't load-bearing.
2. **Structure is quiet, data is warm.** Containers (cards, list rows, nav) use flat neutral surfaces with hairline borders. Only the three macro values get tinted backgrounds — that's the one place color carries meaning.
3. **Dark-mode-first.** Design in dark, verify in light — not the reverse. This app gets opened at meals, often at night.
4. **One accent, used sparingly.** A single accent color for the primary action (the add-food button) and active states. Nothing else competes for that color.
5. **Fast to scan, fast to tap.** Generous tap targets (44px minimum), no ambiguous hover-only affordances — this is a phone-first app.

## 2. Color tokens

Define these as CSS custom properties (works with plain CSS or as a Tailwind theme extension).

```css
:root {
  /* Surfaces — dark mode (default) */
  --bg-page:      #16171a;
  --bg-card:      #1e2024;
  --bg-card-alt:  #26282d;
  --border:       rgba(255,255,255,0.08);
  --border-strong:rgba(255,255,255,0.16);

  /* Text */
  --text-primary:   #f2f2f0;
  --text-secondary: #a3a3a0;
  --text-muted:     #6e6e6c;

  /* Accent (primary actions, active states) */
  --accent:       #7f77dd;   /* soft purple — calm, not alarming */
  --accent-text:  #cecbf6;
  --accent-bg:    rgba(127,119,221,0.16);

  /* Macro pills — semantic, not decorative */
  --protein-text: #85b7eb;
  --protein-bg:   rgba(133,183,235,0.16);
  --carbs-text:   #97c459;
  --carbs-bg:     rgba(151,196,89,0.16);
  --fat-text:     #efa927;
  --fat-bg:       rgba(239,169,39,0.16);

  /* Status (over target, streak, etc.) */
  --success: #97c459;
  --warning: #efa927;
  --danger:  #e24b4a;
}

@media (prefers-color-scheme: light) {
  :root {
    --bg-page:      #f7f6f2;
    --bg-card:      #ffffff;
    --bg-card-alt:  #f1efe8;
    --border:       rgba(0,0,0,0.08);
    --border-strong:rgba(0,0,0,0.14);

    --text-primary:   #1e1e1c;
    --text-secondary: #5f5e5a;
    --text-muted:     #8a8985;

    --accent:      #534ab7;
    --accent-text: #3c3489;
    --accent-bg:   #eeedfe;

    --protein-text: #185fa5;
    --protein-bg:   #e6f1fb;
    --carbs-text:   #3b6d11;
    --carbs-bg:     #eaf3de;
    --fat-text:     #854f0b;
    --fat-bg:       #faeeda;
  }
}
```

**Rule:** macro colors are semantic and fixed — protein is always the blue pair, carbs always green, fat always amber, everywhere in the app (log rows, charts, history). Never reuse these three hues for anything else, or the color loses its meaning.

## 3. Typography

| Role | Size | Weight | Token use |
|---|---|---|---|
| Big number (calorie total) | 26px | 500 | Daily total, only place this large |
| Section label | 15px | 500 | "Today", "Logged", screen titles |
| Body / list item name | 13–14px | 500 | Food names in log rows |
| Secondary / meta | 11–13px | 400 | Timestamps, serving size, macro labels |
| Micro | 11px | 400 | Pill labels ("protein", "carbs", "fat") |

- Two weights only: 400 (regular) and 500 (medium/bold). Never heavier — it fights the calm tone.
- Sentence case everywhere. No ALL CAPS except deliberately in a "brutalist mode" if you ever add a theme toggle — not the default.
- System font stack is fine (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`) — no need to load a custom font for a personal utility app.

## 4. Spacing & radius

```css
--radius-sm: 8px;    /* pills, small controls */
--radius-md: 12px;   /* cards, list rows */
--radius-lg: 16px;   /* modals, sheets */

--space-xs: 4px;
--space-sm: 8px;
--space-md: 12px;
--space-lg: 16px;
--space-xl: 24px;
```

- Card padding: `16px`.
- Gap between macro pills: `8px`.
- Gap between list rows: `6px`.
- No shadows. Depth comes from a one-shade-lighter background (`--bg-card` vs `--bg-page`), not drop shadows.

## 5. Core components

### Macro pill
Tinted background, colored text (same hue pair), label above value.
```html
<div class="macro-pill macro-pill--protein">
  <span class="macro-label">protein</span>
  <span class="macro-value">88g</span>
</div>
```
```css
.macro-pill { flex: 1; border-radius: var(--radius-sm); padding: 8px 6px; text-align: center; }
.macro-pill--protein { background: var(--protein-bg); }
.macro-pill--protein .macro-value,
.macro-pill--protein .macro-label { color: var(--protein-text); }
.macro-label { font-size: 11px; display: block; }
.macro-value { font-size: 14px; font-weight: 500; display: block; }
```

### Log row
Flat card, hairline border, name + meta on the left, calorie count on the right.
```css
.log-row {
  background: var(--bg-card);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.log-row .name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.log-row .meta { font-size: 11px; color: var(--text-muted); }
.log-row .kcal { font-size: 13px; color: var(--text-secondary); }
```

### Primary action (add food)
Only element allowed to use `--accent` as a fill. Circular FAB or full-width button depending on screen.
```css
.btn-primary {
  background: var(--accent);
  color: #ffffff;
  border: none;
  border-radius: var(--radius-sm);
  min-height: 44px;
  font-weight: 500;
}
.btn-secondary {
  background: transparent;
  border: 0.5px solid var(--border-strong);
  color: var(--text-primary);
  min-height: 44px;
  border-radius: var(--radius-sm);
}
```

### Daily total card
The one place text is allowed to be large (26px). Everything else in the card stays small so the total reads as the hero number.
```css
.total-card { background: var(--bg-card); border: 0.5px solid var(--border); border-radius: var(--radius-md); padding: 16px; }
.total-card .kcal-total { font-size: 26px; font-weight: 500; }
.total-card .kcal-goal { font-size: 14px; color: var(--text-muted); font-weight: 400; }
```

## 6. States & feedback

- **Over calorie target:** total number switches to `--danger` — the only place red appears outside explicit delete actions.
- **Empty state (no logs yet today):** short invitation text + the add button, not an apology. E.g. "Nothing logged yet" + "Add food" button — no illustration needed, keep it text-only and calm.
- **Loading (food search):** skeleton rows using `--bg-card-alt`, not a spinner — feels faster for a list-heavy UI.
- **Tap feedback:** `scale(0.98)` + slight background shift on `:active`, no ripple effects.

## 7. Accessibility notes

- Minimum tap target 44×44px for anything interactive (list rows, buttons, macro pills if they become tappable later).
- Macro colors must never be the only signal — always pair with the text label ("protein", "carbs", "fat"), never rely on color alone since some users may have color vision deficiency.
- Contrast: `--text-primary` on `--bg-page`/`--bg-card` and `--protein-text`/`--carbs-text`/`--fat-text` on their respective `-bg` tints should all meet at least WCAG AA (4.5:1) — verify with a contrast checker once real hex values are finalized in code, since rgba-over-dark-bg can shift effective contrast.

## 8. What this deliberately avoids

- No gradients, drop shadows, glow, or neon — flat surfaces only.
- No more than one accent color system-wide.
- No decorative icons or illustrations in the MVP — text and numbers only, icons only where they replace a word (e.g. a trash icon on a delete action).
- No dense data tables in the mobile view — the log list stays row-based, not tabular.
