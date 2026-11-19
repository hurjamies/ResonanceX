# Brand system

## Identity

* **Parent brand:** RESONANCEX (public), ResonanceX (editorial), `resonancex` (repo/namespace)
* **Category:** Personal Resonance Intelligence
* **Tagline:** *Decode what moves you.* · **Statement:** *Discover. Decode. Create. Evolve.*
* **Mission:** To reveal the hidden patterns behind personally meaningful sensory experiences and transform that understanding into new creative possibilities.

Tone: sophisticated, mysterious, technological, emotionally intelligent and personal. It is scientific
inquiry, not mysticism. Subjective, spiritual or archetypal experiences are valid *reports*, never claims of
measurement.

## Product architecture (do not add new top-level brands without a strong reason)

| Name | Role | Tagline | Icon (`design-system/brand.tsx`) |
| --- | --- | --- | --- |
| RESONANCEX | Platform | Decode what moves you. | `ResonanceMark` |
| SonicDNA | Music intelligence | Discover your sonic fingerprint. | `SonicIcon` — waveform in a resonance ring |
| VisualDNA | Visual intelligence | Discover what your eyes feel. | `VisualIcon` — wavefront aperture |
| Resonance Core | Learning and evidence layer | The intelligence behind your experience. | `CoreIcon` — two interfering sources |
| Fusion Studio | Multimodal creation | Where sound becomes vision. | `FusionIcon` — wave entering a frame |
| Resonance Atlas | Discovery map | Explore your inner universe. | `AtlasIcon` — constellation in a field |
| Prompt Studio | Functional workspace (not a top-level brand) | — | `PromptIcon` |

Names are provisional from a trademark perspective.

## Logo

`ResonanceMark` (also `apps/web/public/favicon.svg`) has three concentric resonance wavefronts in
violet with decreasing opacity, a cyan waveform crossing the field, and a gold point of human
perception at the centre. Avoid DNA helices, brains, robots and music notes. The wordmark is
`RESONANCE` + violet `X` in Space Grotesk with wide tracking.

## Colour tokens (`apps/web/src/styles.css`)

| Token | Hex | Use |
| --- | --- | --- |
| `obsidian` | `#0B0F19` | App background |
| `midnight` | `#151A2B` | Panels, dialogs |
| `surface` | `#20263B` | Elevated surfaces, inputs |
| `violet` | `#8B5CF6` | Primary action, resonance, focus glow |
| `cyan` | `#38BDF8` | Sonic data, playhead/selection, measured badges |
| `lavender` | `#D4A5F9` | Visual/harmonic data, estimates |
| `gold` | `#D9BB81` | Human experience, self-reported data, generated media |
| `ink` | `#F5F3FF` | Primary text |
| `muted` | `#9CA9BE` | Secondary text |

The experience is dark-first. Glows are restrained and only signal focus, activity or selection. There is
no heavy glassmorphism, no chaotic neon and no oversized gradients.

## Typography

Space Grotesk (display, headings, numbers), Inter (UI text) and JetBrains Mono (technical data, eyebrows,
prompts). All fonts are bundled locally through `@fontsource`; no external font requests are made.

## Signature element: the Resonance Field

`components/ResonanceField.tsx` places items in a declared feature space (PCA or chosen feature
axes). Rated items emit wavefronts whose amplitude follows the user's reported resonance, and nearby items
interfere. Library items are white, Suno results gold, unrated items grey. A caption always states the
method. It is never presented as a map of consciousness, and it never shows fabricated points.

## Motion

Subtle field pulses, the analysis-stage pulse, a smooth playhead, and fade-in page transitions.
`prefers-reduced-motion` disables animation globally, and the Resonance Field renders statically.

## Evidence and category language

Evidence badges (`EvidenceBadge`) use 0–3 bars plus text: *Ei riittävästi näyttöä · Havainto · Alustava
hypoteesi · Toistuvasti tuettu*. Category badges (`CategoryBadge`) are *Mitattu · Algoritminen arvio ·
Mallin ennuste · Oma kokemus · Tilastollinen yhteys · Tulkinta / hypoteesi*. Colour is never the only
signal: text always accompanies it.
