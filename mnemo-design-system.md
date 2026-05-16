# MNEMO_ Design System v1.0

> Prompt this file to Claude Code when building Mnemo UI. Follow every rule exactly. Do not introduce colours, typefaces, or motion not listed here.

---

## 1. Brand

**Name:** Mnemo. Always capitalised. Never with a full stop.
**Wordmark:** `MNEMO_` — the trailing underscore is part of the mark, rendered in Cyan Pulse.
**Tagline (primary):** Remember everything.

**Personality:** Precise. Quiet confidence. Engineered, not styled. Retro-informed, not retro-themed.

---

## 2. Colour

Use only these values. No other colours permitted.

| Token | Hex | Usage |
|---|---|---|
| `--color-bg` | `#0A0A0F` | App background |
| `--color-surface` | `#12121A` | Sidebar, panels, surfaces |
| `--color-border` | `#1A1A2E` | All borders and dividers |
| `--color-accent` | `#00E5FF` | Primary accent, `#tags`, icon cursor, active states |
| `--color-ref` | `#7FDFFF` | `@references` |
| `--color-text` | `#E8E8F0` | Primary text |
| `--color-muted` | `#7878A0` | Secondary text, metadata, inactive items |

**Tag highlight:** `#00E5FF` at 15% opacity background.
**Reference highlight:** `#7FDFFF` at 8% opacity background.

### CSS custom properties

```css
:root {
  --color-bg:      #0A0A0F;
  --color-surface: #12121A;
  --color-border:  #1A1A2E;
  --color-accent:  #00E5FF;
  --color-ref:     #7FDFFF;
  --color-text:    #E8E8F0;
  --color-muted:   #7878A0;
  --font-mono:     'IBM Plex Mono', 'Courier New', monospace;
}
```

---

## 3. Typography

One typeface only: **IBM Plex Mono**. Load weights 400 and 500. No other typefaces permitted. Fallback: `'Courier New', monospace`.

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap');
```

| Role | Size | Weight | Notes |
|---|---|---|---|
| App wordmark | 13px | 500 | Letter-spacing 0.2em. Always caps. |
| Screen headings | 16px | 500 | Tight tracking. |
| Body / note text | 13px | 400 | Line-height 1.9. |
| Sidebar items | 11px | 400 | Secondary: `--color-muted`. |
| Metadata / labels | 9–10px | 400 | Uppercase. Letter-spacing 0.1em. |
| Keyboard shortcuts | 9px | 400 | `--color-muted`. Boxed with 1px `--color-border`. |

---

## 4. Layout

Two-panel layout:

- **Title bar** — full width, `--color-surface`, 1px `--color-border` bottom edge.
- **Sidebar** — 200px fixed, `--color-surface`, 1px `--color-border` right edge.
- **Editor** — flex: 1, `--color-bg`.
- **Toolbar** — full editor width, pinned to bottom, 1px `--color-border` top edge.

No drop shadows between panels. No gradients. Hard edges only.

---

## 5. Components

### Title bar

```
| MNEMO_   [status text — right aligned, --color-muted, 10px] |
```

- Height: ~36px
- Background: `--color-surface`
- Bottom border: 1px `--color-border`

### Sidebar note item

```css
.note-item {
  padding: 8px 16px;
  font-size: 11px;
  color: var(--color-muted);
  border-left: 2px solid transparent;
  line-height: 1.4;
}
.note-item.active {
  color: var(--color-text);
  border-left-color: var(--color-accent);
  background: var(--color-bg);
}
.note-item:hover:not(.active) {
  color: #B0B0C8;
  background: #0F0F18;
}
```

Each note item shows:
- Note title (primary text)
- Below: date + `#tag` — 9px, `--color-muted`, uppercase

### Section labels (sidebar)

```css
.section-label {
  font-size: 9px;
  color: var(--color-muted);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  padding: 0 16px 8px;
}
```

### #tag rendering

```css
.tag {
  display: inline-block;
  font-size: 9px;
  color: var(--color-accent);
  background: rgba(0, 229, 255, 0.15);
  padding: 3px 8px;
  border-radius: 2px;
  letter-spacing: 0.05em;
}
```

### @reference rendering

```css
.ref {
  display: inline-block;
  font-size: 9px;
  color: var(--color-ref);
  background: rgba(127, 223, 255, 0.08);
  padding: 3px 8px;
  border-radius: 2px;
  letter-spacing: 0.05em;
}
```

### Tag and reference regex

```js
// #tags — apply .tag class
/(#[a-zA-Z0-9_-]+)/g

// @references — apply .ref class
/(@[a-zA-Z0-9_-]+)/g
```

### Cursor

```css
.cursor {
  display: inline-block;
  width: 8px;
  height: 14px;
  background: var(--color-accent);
  vertical-align: middle;
  animation: blink 1.1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
```

### Keyboard shortcut display

```css
.shortcut-key {
  font-size: 9px;
  color: var(--color-muted);
  border: 1px solid var(--color-border);
  padding: 2px 5px;
  border-radius: 2px;
  margin-right: 4px;
}
```

Render as: `<span class="shortcut-key">⌘S</span> save`

### Toolbar

```
| [shortcut] label   [shortcut] label   [shortcut] label  |  247 CHARS · 2 TAGS |
```

- Background: `--color-surface`
- Top border: 1px `--color-border`
- Padding: 10px 24px
- Font: 9px, `--color-muted`, letter-spacing 0.1em
- Char/tag count: right-aligned

---

## 6. Scanline Texture

Apply to sidebar and background surfaces only. Do not apply to the editor body.

```css
.scanlines {
  background: repeating-linear-gradient(
    to bottom,
    transparent 0px,
    transparent 3px,
    rgba(0, 0, 0, 0.08) 3px,
    rgba(0, 0, 0, 0.08) 4px
  );
}
```

---

## 7. Motion

Minimal. Do not add animation beyond what is listed here.

| Element | Animation | Spec |
|---|---|---|
| Text cursor | Step blink | 1.1s, step-end, infinite |
| Hover states | Background fill | Immediate (0ms) |
| Active states | Border change | Immediate (0ms) |
| All other transitions | None | Instant |

---

## 8. Icon

The app icon is a geometric M with a Cyan Pulse vertical cursor line bisecting it at the axis. A small cursor block sits at the base of the line.

- Icon background: `#0A0A0F`
- M strokes: `#E8E8F0`, stroke-width 9px, square linecaps
- Cursor line: `#00E5FF`, 4px wide
- Cursor block: `#00E5FF`, 8×16px, at base of cursor line

Corner radius by platform:

| Platform | Radius |
|---|---|
| iOS | 36px (on 200px icon) |
| Android / Web | 20px |
| macOS | 8px |
| Favicon (32×32) | 4px or 0px |

**Rules:**
- Never place the icon on a light background
- Never recolour the cursor element
- Minimum display size: 24×24px
- No drop shadows or glows

---

## 9. Tone of Voice

UI copy: precise and minimal. Every string earns its place.

| Do | Do not |
|---|---|
| `12 notes` | `You have 12 notes saved` |
| `Saved.` | `Your note has been saved successfully!` |
| `No notes yet.` | `It looks like you haven't created any notes yet.` |
| `New note  ⌘N` | `Click here to create a brand new note` |
| `Error. Try again.` | `Oops! Something went wrong. Please try again later.` |

- Labels: lowercase where possible
- Status messages: sentence-case, ends with full stop
- Errors: plain statements, not apologies
- No exclamation marks

---

## 10. What Not to Do

- Do not use any colour not listed in section 2
- Do not use any typeface other than IBM Plex Mono
- Do not add drop shadows, gradients, glows, or blur
- Do not add motion beyond section 7
- Do not round corners beyond 4px except on the app icon
- Do not place the wordmark or icon on a light background
- Do not add decorative elements of any kind
