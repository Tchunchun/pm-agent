# PM Strategy Copilot — UI/UX Design Guideline

> **Version:** 1.0  
> **Last updated:** 2026-02-27  
> **Design reference:** Claude Code (Anthropic) — compact, professional, terminal-inspired aesthetic  

---

## 1. Design Philosophy

| Principle | Description |
|-----------|-------------|
| **Information-dense** | Maximise content per viewport; avoid decorative whitespace |
| **Readable at any zoom** | Use `rem`-based sizing so everything scales with browser zoom |
| **Quiet chrome** | UI controls recede; content is the hero |
| **Consistent rhythm** | 4 px base grid; spacing always multiples of 4 |
| **Dark-mode ready** | Colour tokens defined as CSS variables for future theme switching |

---

## 2. Typography

### 2.1 Font Stack

```css
/* Primary — UI text */
--font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
             Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue",
             sans-serif;

/* Monospace — code, IDs, keys, agent @mentions */
--font-mono: "JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code",
             "Source Code Pro", Menlo, Consolas, "Liberation Mono",
             monospace;
```

### 2.2 Type Scale (rem-based)

All sizes are relative to a **13 px root** (`html { font-size: 13px }`), matching the compact density of Claude Code.

| Token | rem | ~px | Usage |
|-------|-----|-----|-------|
| `--text-2xs` | 0.692rem | 9 | Micro-labels, timestamps, footnotes |
| `--text-xs`  | 0.769rem | 10 | Badges (P0, P1…), captions, metadata |
| `--text-sm`  | 0.846rem | 11 | Secondary text, descriptions, hints |
| `--text-base`| 1rem     | 13 | Body copy, chat messages, form labels |
| `--text-md`  | 1.077rem | 14 | Card titles, table headers |
| `--text-lg`  | 1.231rem | 16 | Section headings (h3 equivalent) |
| `--text-xl`  | 1.385rem | 18 | Page headings (h2 equivalent) |
| `--text-2xl` | 1.692rem | 22 | Top-level heading (h1, used sparingly) |

### 2.3 Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| `--weight-normal`   | 400 | Body text, descriptions |
| `--weight-medium`   | 500 | Labels, active nav items |
| `--weight-semibold` | 600 | Card titles, section headers, emphasis |
| `--weight-bold`     | 700 | Page headings, stat values, badges |

### 2.4 Line Heights

| Context | Value |
|---------|-------|
| Headings | 1.3 |
| Body / UI | 1.5 |
| Compact (badges, pills) | 1.2 |
| Monospace blocks | 1.55 |

### 2.5 Letter Spacing

| Context | Value |
|---------|-------|
| Uppercase labels / section headers | 0.06em |
| Body text | normal (0) |
| Monospace | -0.01em |

---

## 3. Colour System

### 3.1 Neutral Palette (Slate)

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-bg`        | #ffffff | Page background |
| `--color-surface`   | #f8fafc | Card / panel backgrounds |
| `--color-surface-2` | #f1f5f9 | Hover states, secondary surfaces |
| `--color-border`    | #e2e8f0 | Default borders |
| `--color-border-active` | #93c5fd | Active / focused borders |
| `--color-text`      | #1e293b | Primary text |
| `--color-text-secondary` | #475569 | Secondary text, descriptions |
| `--color-text-muted`| #94a3b8 | Placeholders, disabled, metadata |

### 3.2 Accent Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-accent`    | #3b82f6 | Primary actions, active states |
| `--color-accent-bg` | #eff6ff | Active card/tab background |
| `--color-accent-hover` | #2563eb | Button hover |

### 3.3 Semantic Colours

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-p0` | #dc2626 | P0 Critical |
| `--color-p1` | #ea580c | P1 High |
| `--color-p2` | #ca8a04 | P2 Medium |
| `--color-p3` | #65a30d | P3 Low |
| `--color-success` | #16a34a | Success states |
| `--color-warning` | #d97706 | Warnings |
| `--color-error`   | #dc2626 | Errors |
| `--color-info`    | #2563eb | Info banners |

### 3.4 Insight Type Colours

| Type | Border Colour | Token |
|------|--------------|-------|
| Risk | #dc2626 | `--color-insight-risk` |
| Trend | #2563eb | `--color-insight-trend` |
| Gap | #ca8a04 | `--color-insight-gap` |
| Decision | #7c3aed | `--color-insight-decision` |

---

## 4. Spacing & Layout

### 4.1 Spacing Scale (4 px grid)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight inline gaps |
| `--space-2` | 8px | Between related elements (icon + label) |
| `--space-3` | 12px | Card internal padding, list item gaps |
| `--space-4` | 16px | Standard card padding, section gaps |
| `--space-5` | 20px | Between sections |
| `--space-6` | 24px | Major section breaks |
| `--space-8` | 32px | Page-level breathing room |

### 4.2 Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Badges, pills, small buttons |
| `--radius-md` | 6px | Inputs, small cards |
| `--radius-lg` | 8px | Cards, panels |
| `--radius-xl` | 10px | Modals, large surfaces |

### 4.3 Streamlit Layout

| Zone | Width | Notes |
|------|-------|-------|
| Sidebar | default (st) | Compact stats, nav |
| Main container | `layout="wide"` | Full viewport |
| Chat left panel | 1 col (of 4) | Workroom list |
| Chat right panel | 3 cols (of 4) | Chat + controls |
| Chat message area | `height=460px` | Scrollable |
| Quick-chat area | `height=420px` | Scrollable |

---

## 5. Component Patterns

### 5.1 Cards

```
┌─ 1px border (--color-border) ─────────────────────┐
│  padding: --space-3 --space-4                      │
│  border-radius: --radius-lg                        │
│                                                    │
│  Title .........  --text-md / --weight-semibold    │
│  Meta line .....  --text-xs / --color-text-muted   │
└────────────────────────────────────────────────────┘
```

- **Default state:** white bg, light border  
- **Hover state:** `--color-surface-2` bg, `--color-border-active` border  
- **Active state:** `--color-accent-bg` bg, 2 px `--color-accent` border  

### 5.2 Stat Cards

```
┌─ gradient surface bg ──────────────────────────────┐
│  text-align: center                                │
│  padding: --space-4                                │
│                                                    │
│          VALUE  --text-xl / --weight-bold           │
│          LABEL  --text-xs / uppercase               │
└────────────────────────────────────────────────────┘
```

### 5.3 Badges / Pills

- Height: ~20 px  
- Padding: 2px 8px  
- Font: `--text-xs` / `--weight-bold`  
- Border-radius: `--radius-sm` (12px for fully rounded)  
- Semantic colours for priority; neutral for status  

### 5.4 Section Headers

- Font: `--text-xs` / `--weight-bold`  
- Transform: uppercase  
- Letter-spacing: 0.06em  
- Colour: `--color-text-muted`  
- Margin: `--space-3` top, `--space-2` bottom  

### 5.5 Empty States

- Centered layout  
- Icon: `--text-2xl` (emoji)  
- Text: `--text-sm` / `--color-text-muted`  
- Padding: `--space-8` vertical  

### 5.6 Chat Messages

- Agent avatar badge: `--text-xs` / `--weight-semibold` in a pill  
- Message body: `--text-base`  
- Monospace for code blocks  

### 5.7 Buttons

| Variant | Background | Text | Border |
|---------|-----------|------|--------|
| Primary | `--color-accent` | white | none |
| Secondary | transparent | `--color-text` | `--color-border` |
| Danger | transparent | `--color-error` | `--color-error` |

Font: `--text-sm` / `--weight-medium`

---

## 6. Streamlit-Specific Overrides

Since Streamlit controls its own components, we use `<style>` injection to override:

```css
/* Root font size — controls all rem values */
html, body, [data-testid="stAppViewContainer"] {
  font-size: 13px !important;
  font-family: var(--font-sans) !important;
}

/* Page padding */
.block-container { padding-top: 1.2rem; }

/* Sidebar  */
[data-testid="stSidebar"] { font-size: 13px; }

/* Markdown headings */
.stMarkdown h1 { font-size: var(--text-2xl); }
.stMarkdown h2 { font-size: var(--text-xl); }
.stMarkdown h3 { font-size: var(--text-lg); }

/* Tabs */
.stTabs [data-baseweb="tab"] { font-size: var(--text-sm); }

/* Inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
  font-size: var(--text-base);
  font-family: var(--font-sans);
}

/* Chat input */
[data-testid="stChatInput"] textarea { font-size: var(--text-base); }

/* Captions */
.stCaption { font-size: var(--text-xs) !important; }

/* Expander summary */
.streamlit-expanderHeader { font-size: var(--text-sm); }
```

---

## 7. Accessibility

| Requirement | Standard |
|-------------|----------|
| Min contrast (body) | 4.5:1 WCAG AA |
| Min contrast (large text) | 3:1 WCAG AA |
| Min tap target | 44 × 44 px |
| Focus ring | 2 px offset, `--color-accent` |
| Font size floor | Never below 9 px rendered |

---

## 8. Responsive Behaviour

Streamlit handles most responsiveness. Additional rules:

| Breakpoint | Behaviour |
|------------|-----------|
| < 768 px | Sidebar auto-collapses; stat cards stack |
| 768–1200 px | 2-col chat layout maintained |
| > 1200 px | Full wide layout |

---

## 9. Iconography

- **Emoji-first** for agent avatars, tab labels, section headers  
- Consistent emoji set (no mixing between platforms)  
- Avoid icon-only buttons — always pair with short label text  

---

## 10. Naming Conventions (CSS Classes)

| Prefix | Scope |
|--------|-------|
| `.wr-*` | Workroom components |
| `.agent-*` | Agent-related UI |
| `.stat-*` | Stat dashboard cards |
| `.badge-*` | Priority / status badges |
| `.insight-*` | Insight type styling |
| `.empty-*` | Empty state containers |
| `.section-*` | Section-level helpers |
| `.focus-*` | Focus/today items |
| `.meeting-*` | Meeting strips |

---

## 11. Implementation Checklist

When adding a new feature or component:

1. [ ] Use design tokens (CSS variables) — never hard-code hex/px
2. [ ] Typography from the type scale — no arbitrary sizes
3. [ ] Spacing from the 4 px grid
4. [ ] Test at browser zoom 90%, 100%, 125%, 150%
5. [ ] Ensure 4.5:1 contrast on all text
6. [ ] Add empty state for lists that can be empty
7. [ ] Use `st.caption()` for metadata, not `st.markdown()` with small text
8. [ ] Follow the CSS class naming convention
