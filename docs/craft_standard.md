# Facelift Craft Standard

The difference between "clean" and "unforgettable," codified. Every build
targets the highest level its complexity-tier allows; the quality gate
enforces the minimums of that level. Inspired by elite web design practice,
constrained to Facelift's reality: vanilla HTML/CSS/JS, zero CDNs, ₹0
hosting, mobile-first Indian bandwidth.

## Levels (maps to PRD complexity)

| Tier | Bar | Applies to |
|---|---|---|
| **C1 Good** | Clean layout, solid type, deliberate colors | every build (floor) |
| **C2 Excellent** | Art direction + choreographed motion + polish | default target (L1/L2 builds) |
| **C3 Exceptional** | Distinct visual world + scroll storytelling + signature interaction | Growth/Premium builds |
| **C4 Never-seen** | The interface itself is the brand experience | flagship cases only, never forced |

## 1. Art direction before animation

Someone should recognize the site from a screenshot WITHOUT the logo.

- **Trade motif**: derive one repeating visual idea from the business type
  (hostel = route/journey lines · restaurant = menu-card frames & dotted
  dividers · clinic = calm cross/plus grid · salon = soft arcs · gym =
  bold diagonal energy cuts · generic local = map-pin / neighborhood grid).
- Typography: pick a distinctive display treatment (weight contrast,
  tracking, oversized numerals for stats) — system fonts styled bravely.
- Color system: base (warm off-white OR deep near-black) + ONE brand color
  (from mined tokens when available) + 2–3 strategic accents + atmosphere
  (one subtle gradient/glow/grain max).
- Consistent shape language: one radius family, one border style, one
  shadow recipe used everywhere.
- Photography: real photos treated consistently (same duotone/overlay/
  crop ratio); concept art labeled gen-* follows the same grade.

## 2. Motion choreography (not decoration)

Sequenced reveals, never everything-at-once:

```
background shifts → headline slides in → image expands →
supporting text fades → CTA settles
```

Vanilla toolkit (all allowed): CSS transitions/keyframes,
IntersectionObserver staggers (60–120ms steps), `position: sticky`
scene-pinning, scroll-linked class toggles, `scroll-behavior: smooth`,
view-transition-style crossfades between sections.
Motion serves hierarchy: entrance order = reading order. Honor
`prefers-reduced-motion` always.

## 3. Depth

Layer foreground/midground/background: overlapping cards, floating accent
shapes, translucent panels, real shadows (soft, directional), parallax on
ONE layer max, scale contrast between sections. The page should feel like
a space being moved through, not a document being scrolled.

## 4. Micro-interactions (pick ≥4)

Cursor-reactive cards (tilt/glow-follow) · magnetic buttons · icon-slide
links · image zoom-on-hover with caption slide · nav active-indicator that
physically travels · counters that count up on reveal · copy-to-clipboard
with feedback · form fields that breathe on focus.

## 5. Scroll storytelling

Sections transform INTO each other (color/shape/scale handoffs), not hard
cuts. One pinned "scene" per page maximum. Background color journey tied
to narrative chapters is the highest-value, lowest-cost trick.

## 6. Signature interaction (from TRADE PLAYBOOK)

Each vertical's playbook defines one working end-to-end component
(room-selector composer, tap-to-order basket, appointment composer…).
It must be flawless — this is the demo moment.

## 7. Rich media restraint

SVG line-drawings, canvas particle accents, masked image reveals are all
welcome IF dependency-free. No WebGL/3D libraries unless a Premium client
explicitly pays for that tier. A perfectly art-directed 2D site beats an
unconceptual 3D gimmick every time.

## 8. Sound

Default OFF. If used (Premium only): opt-in toggle, tiny assets, spatial
subtlety. Never autoplay.

## 9. Performance law (non-negotiable, part of the design)

Page weight ≤ 250KB total (incl. images) · LCP <2s · CLS <0.1 · 60fps
interactions · no jank on ₹8k Android phones · reduced-motion respected.
If an effect risks the budget, replace it with a cheaper illusion of the
same effect. **Stuttering kills premium faster than plainness.**

## Gate mapping (automated checks)

C2 floor enforced by `quality_check`: sections≥3 · :hover present ·
motion present · OG+image · contact actions · no lorem · size sane.
C2+ signals checked: staggered transition-delays · sticky positioning ·
layered z-index composition · custom properties theme system · signature
component selector present · scroll-story class structure.
