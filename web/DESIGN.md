---
version: alpha
name: CodePulse-design-analysis
description: "A near-black dashboard canvas built around #050505 (the deepest surface), light gray text (#e8e8e8), and a signature teal-emerald accent (#2dd4bf) used as the single chromatic accent on an otherwise monochrome developer tool. The system reads as a code graph explorer: dark, technical, and data-dense. Display type is set in Geist (SF Pro fallback) at 500–600 with negative tracking. Cards live as charcoal panels (#0d0d0d) with hairline borders. The accent teal appears on brand mark, focus rings, graph node highlights, and primary CTAs. Page rhythm leans on the force-directed graph as the dominant visual element — no photography, no illustration."

colors:
  primary: "#2dd4bf"
  on-primary: "#050505"
  primary-hover: "#5eead4"
  primary-focus: "#14b8a6"
  ink: "#e8e8e8"
  ink-muted: "#a1a1aa"
  ink-subtle: "#71717a"
  ink-tertiary: "#52525b"
  canvas: "#050505"
  surface-1: "#0d0d0d"
  surface-2: "#121212"
  surface-3: "#181818"
  surface-4: "#1a1a1a"
  hairline: "#1f1f23"
  hairline-strong: "#2a2a2e"
  hairline-tertiary: "#35353a"
  inverse-canvas: "#ffffff"
  inverse-ink: "#050505"
  semantic-success: "#22c55e"
  semantic-error: "#ef4444"
  semantic-warning: "#f59e0b"
  semantic-overlay: "#000000"
  node-function: "#f59e0b"
  node-class: "#3b82f6"
  node-method: "#8b5cf6"
  node-interface: "#06b6d4"
  node-symbol: "#6b7280"

typography:
  display-xl:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 80px
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: -3.0px
  display-lg:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 56px
    fontWeight: 600
    lineHeight: 1.10
    letterSpacing: -1.8px
  display-md:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 40px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -1.0px
  headline:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.20
    letterSpacing: -0.6px
  card-title:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 22px
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: -0.4px
  subhead:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.40
    letterSpacing: -0.2px
  body-lg:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: -0.1px
  body:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: -0.05px
  body-sm:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: 0
  caption:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.40
    letterSpacing: 0
  button:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.20
    letterSpacing: 0
  eyebrow:
    fontFamily: Geist, -apple-system, system-ui, sans-serif
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.30
    letterSpacing: 0.4px
  mono:
    fontFamily: Geist Mono, ui-monospace, SF Mono, Menlo, monospace
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.50
    letterSpacing: 0

rounded:
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  xxl: 24px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 96px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
  button-secondary:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  button-tertiary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 8px 14px
  text-input:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 8px 12px
  text-input-focused:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 8px 12px
  feature-card:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: 24px
  graph-container:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    border: "1px solid {colors.hairline}"
  detail-card:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: 24px
    border: "1px solid {colors.hairline}"
  status-badge:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: 2px 8px
  top-nav:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    height: 56px
    borderBottom: "1px solid {colors.hairline}"
  footer:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-subtle}"
    typography: "{typography.caption}"
    padding: 32px 24px
---

## Overview

CodePulse is a code intelligence graph dashboard — a developer tool that visualizes code structure as an interactive force-directed graph. The canvas is near-black (`{colors.canvas}` #050505) with a four-step surface ladder for cards and panels. The single chromatic accent is **teal-emerald** `{colors.primary}` (#2dd4bf) — used on the brand mark, focus rings, graph node highlights, and the primary CTA button.

The design language is inspired by Linear: dark-canvas marketing system, surface ladder for hierarchy without shadows, aggressive negative tracking on display type, and product-first visual emphasis. For CodePulse, the "product" is the force-directed graph itself — it occupies the dominant visual position on every page.

**Key Characteristics:**
- **Dark-canvas dashboard** — `{colors.canvas}` (#050505) absorbs the force graph into the surface
- **Teal-emerald brand accent** (`{colors.primary}` #2dd4bf) — used sparingly on CTAs, focus, and graph highlights
- Four-step surface ladder (canvas → surface-1 → surface-2 → surface-3 → surface-4) carries hierarchy without shadow
- Display tracking pulls aggressively negative (-3.0px at 80px); body holds at -0.05px
- Cards use `{rounded.lg}` 12px corners with 1px hairline borders
- **Force-directed graph dominates** — the dashboard chrome is a dark frame for the graph
- Node colors encode symbol types: function=amber, class=blue, method=purple, interface=cyan

## Colors

### Brand & Accent
- **Teal-Emerald** (`{colors.primary}` #2dd4bf): Signature accent — primary CTA, brand mark, focus ring, graph highlight.
- **Teal Hover** (`{colors.primary-hover}` #5eead4): Lighter teal — hovered state of primary CTA.
- **Teal Focus** (`{colors.primary-focus}` #14b8a6): Focus-ring tint for inputs and buttons.

### Surface
- **Canvas** (`{colors.canvas}` #050505): Default page background — near-pure black.
- **Surface 1** (`{colors.surface-1}` #0d0d0d): One step above canvas — feature cards, detail panel.
- **Surface 2** (`{colors.surface-2}` #121212): Two steps above — secondary cards, hovered items.
- **Surface 3** (`{colors.surface-3}` #181818): Three steps above — sub-nav, tertiary surfaces.
- **Surface 4** (`{colors.surface-4}` #1a1a1a): Four steps above — deepest lifted surface.
- **Hairline** (`{colors.hairline}` #1f1f23): 1px borders on cards and dividers.
- **Hairline Strong** (`{colors.hairline-strong}` #2a2a2e): Stronger 1px borders for emphasis.
- **Hairline Tertiary** (`{colors.hairline-tertiary}` #35353a): Tertiary borders for nested surfaces.
- **Inverse Canvas** (`{colors.inverse-canvas}` #ffffff): Pure white — used for inverse pill CTA.

### Text
- **Ink** (`{colors.ink}` #e8e8e8): All headlines and emphasized body type — light gray.
- **Ink Muted** (`{colors.ink-muted}` #a1a1aa): Secondary type for meta info.
- **Ink Subtle** (`{colors.ink-subtle}` #71717a): Tertiary type for footer, captions.
- **Ink Tertiary** (`{colors.ink-tertiary}` #52525b): Quaternary type for disabled states.

### Node Colors (Graph)
- **Function** (`{colors.node-function}` #f59e0b): Amber — function/method definitions.
- **Class** (`{colors.node-class}` #3b82f6): Blue — class definitions.
- **Method** (`{colors.node-method}` #8b5cf6): Purple — method definitions.
- **Interface** (`{colors.node-interface}` #06b6d4): Cyan — interface definitions.
- **Symbol** (`{colors.node-symbol}` #6b7280): Gray — generic symbols.

### Semantic
- **Success** (`{colors.semantic-success}` #22c55e): Status indicators.
- **Error** (`{colors.semantic-error}` #ef4444): Error states.
- **Warning** (`{colors.semantic-warning}` #f59e0b): Warning states.

## Typography

### Font Family

- **Geist** — Vercel's open-source sans-serif; fallback `-apple-system, system-ui, sans-serif`. Carries display-xl through caption.
- **Geist Mono** — Vercel's open-source monospace; fallback `ui-monospace, SF Mono, Menlo`. Used for code snippets and symbol signatures.

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|
| `{typography.display-xl}` | 80px | 600 | 1.05 | -3.0px | Marketing hero headline |
| `{typography.display-lg}` | 56px | 600 | 1.10 | -1.8px | Section opener |
| `{typography.display-md}` | 40px | 600 | 1.15 | -1.0px | Sub-section |
| `{typography.headline}` | 28px | 600 | 1.20 | -0.6px | Dashboard title |
| `{typography.card-title}` | 22px | 500 | 1.25 | -0.4px | Card titles |
| `{typography.subhead}` | 20px | 400 | 1.40 | -0.2px | Lead body |
| `{typography.body-lg}` | 18px | 400 | 1.50 | -0.1px | Hero subtext |
| `{typography.body}` | 16px | 400 | 1.50 | -0.05px | Default body |
| `{typography.body-sm}` | 14px | 400 | 1.50 | 0 | Card body, footer |
| `{typography.caption}` | 12px | 400 | 1.40 | 0 | Captions, meta |
| `{typography.button}` | 14px | 500 | 1.20 | 0 | Button labels |
| `{typography.eyebrow}` | 13px | 500 | 1.30 | 0.4px | Section eyebrow |
| `{typography.mono}` | 13px | 400 | 1.50 | 0 | Code, signatures |

### Principles
- **Aggressive negative tracking on display** (-3.0px at 80px ≈ 4% of size).
- **Single voice**: display-xl at 600 through body at 400 — same family, narrower weights.
- **Mono for code contexts only** — signatures, file paths, symbol IDs.

### Note on Font Substitutes
Geist is open-source from Vercel and already loaded by `create-next-app`. Geist Mono is available at `geist` npm package. For environments without Geist, **Inter** is the closest substitute.

## Layout

### Spacing System
- **Base unit**: 4px.
- **Section padding**: 96px between major sections on desktop, collapsing to 32–48px on mobile.
- **Card interior padding**: 24px on feature cards; 16px on compact detail cards.
- **Form field padding**: 8px vertical, 12px horizontal.

### Grid & Container
- Dashboard centers in a ~1400px container.
- Graph occupies 3/4 of viewport width; detail sidebar occupies 1/4.
- At tablet: sidebar slides to bottom drawer. At mobile: single column graph.

### Whitespace Philosophy
The dark canvas absorbs whitespace. The graph fills the primary area with generous padding around it. Cards lift subtly from canvas via surface ladder. Section spacing uses `{spacing.section}` 96px.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| 0 (flat) | No background, no border | Canvas, body type |
| 1 (charcoal lift) | `{colors.surface-1}` + 1px `{colors.hairline}` | Feature cards, detail panel |
| 2 (surface-2 lift) | `{colors.surface-2}` + 1px `{colors.hairline-strong}` | Hovered cards, active items |
| 3 (surface-3 lift) | `{colors.surface-3}` | Sub-nav, tertiary panels |
| 4 (focus ring) | 2px `{colors.primary-focus}` outline at 50% opacity | Focused inputs |

Depth is carried by surface ladder + hairline borders. No drop shadows.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.xs}` | 4px | Small chips, status badges |
| `{rounded.sm}` | 6px | Inline tags |
| `{rounded.md}` | 8px | All buttons, form inputs |
| `{rounded.lg}` | 12px | Feature cards, detail cards |
| `{rounded.xl}` | 16px | Graph container, oversized panels |
| `{rounded.xxl}` | 24px | CTA banners |
| `{rounded.pill}` | 9999px | Status pills, badges |

## Components

### Buttons

**`button-primary`** — Teal CTA. The default primary CTA.
- Background `{colors.primary}`, text `{colors.on-primary}`, type `{typography.button}`, padding 8px 14px, rounded `{rounded.md}`.
- Hover: `button-primary-hover` (background shifts to `{colors.primary-hover}` lighter teal).

**`button-secondary`** — Charcoal button. Used for secondary actions.
- Background `{colors.surface-1}`, text `{colors.ink}`, type `{typography.button}`, padding 8px 14px, rounded `{rounded.md}`. 1px `{colors.hairline}` border.

**`button-tertiary`** — Plain text button.
- Background `{colors.canvas}`, text `{colors.ink}`, type `{typography.button}`, rounded `{rounded.md}`.

### Cards & Containers

**`feature-card`** — Generic feature card.
- Background `{colors.surface-1}`, text `{colors.ink}`, type `{typography.body}`, rounded `{rounded.lg}`, padding 24px, 1px `{colors.hairline}` border.

**`graph-container`** — The force-directed graph container.
- Background `{colors.canvas}`, text `{colors.ink}`, rounded `{rounded.xl}`, 1px `{colors.hairline}` border.

**`detail-card`** — Node detail sidebar panel.
- Background `{colors.surface-1}`, text `{colors.ink}`, type `{typography.body}`, rounded `{rounded.lg}`, padding 24px, 1px `{colors.hairline}` border.

**`status-badge`** — Status pill.
- Background `{colors.surface-2}`, text `{colors.ink-muted}`, type `{typography.caption}`, rounded `{rounded.pill}`, padding 2px 8px.

### Inputs

**`text-input`** + **`text-input-focused`** — Search bar and form fields.
- Background `{colors.surface-1}`, text `{colors.ink}`, type `{typography.body}`, rounded `{rounded.md}`, padding 8px 12px.
- Focused: 2px `{colors.primary-focus}` outline at 50% opacity.

### Navigation

**`top-nav`** — Sticky dark bar with brand wordmark left, search right.
- Background `{colors.canvas}`, text `{colors.ink}`, type `{typography.body-sm}`, height 56px, 1px `{colors.hairline}` bottom border.

### Footer

**`footer`** — Lightweight stats bar.
- Background `{colors.canvas}`, text `{colors.ink-subtle}`, type `{typography.caption}`, padding 32px 24px.

## Graph Component Spec

The force-directed graph is the product's protagonist:

- **Canvas**: `{colors.canvas}` — the graph background IS the page background.
- **Nodes**: Filled circles, radius 6px, stroke `{colors.ink}` at 30% on hover.
- **Node colors**: `{colors.node-function}` amber, `{colors.node-class}` blue, `{colors.node-method}` purple, `{colors.node-interface}` cyan, `{colors.node-symbol}` gray.
- **Edges**: 1px stroke `{colors.hairline}` at 40% opacity.
- **Selected node**: 2px `{colors.primary}` stroke, scale 1.3× with spring animation.
- **Labels**: `{typography.caption}` in `{colors.ink-muted}`, placed 8px right of node center.
- **Zoom**: scale 0.1–4×, smooth d3-zoom with `{animation.spring}` feel.
- **Simulation**: d3 force with link distance 80, charge -150, center gravity.

## Do's and Don'ts

### Do
- Reserve `{colors.primary}` teal for: brand mark, primary CTA, focus ring, graph highlights.
- Use the four-step surface ladder for hierarchy.
- Apply negative letter-spacing on display tiers.
- Let the force graph dominate the viewport — it is the product.
- Use tight `{rounded.md}` 8px for CTAs — never pill shapes.
- Render signatures and file paths in `{typography.mono}`.

### Don't
- Don't introduce a second chromatic accent.
- Don't use teal as a section background or card fill.
- Don't add shadows — use surface ladder instead.
- Don't use pure black `#000000` as canvas.
- Don't pill-round CTAs.
- Don't place decorative elements that compete with the graph.

## Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|---|---|---|
| Desktop | ≥ 1200px | Graph 3/4 + sidebar 1/4 |
| Tablet | 768–1199px | Sidebar slides to bottom drawer |
| Mobile | < 768px | Single column; nav compact |

### Touch Targets
- CTAs hold ≥40px tap height.
- Form inputs hold ≥44px tap target on touch.
- Graph nodes scale tap target with zoom level.

### Collapsing Strategy
- **Top nav**: links on desktop, hamburger below 768px.
- **Graph + sidebar**: side-by-side on desktop → graph full-width with bottom drawer on tablet → stacked on mobile.
- **Display type**: scales proportionally.

### Image Behavior
No photography. The force-directed graph is the only visual element.

## Iteration Guide

1. Focus on ONE component at a time.
2. Reference component names and tokens directly.
3. Default body to `{typography.body}` at weight 400.
4. Keep teal scarce: brand mark, primary CTA, focus, graph highlight.
5. Lead every view with the force graph.
