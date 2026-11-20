# RESONANCEX

**Personal Resonance Intelligence — Decode what moves you.**
*Discover. Decode. Create. Evolve.*

ResonanceX is a local-first application for systematically exploring which properties of
music move *you*, physically, emotionally and subjectively, and for turning that understanding
into creative instructions for generative AI (Suno first).

It is not a recommender or a genre classifier. It keeps five kinds of knowledge apart:
**measured** signal properties, **algorithmic estimates**, **self-reported** experiences,
**statistical relationships**, and **interpretive** hypotheses. See
[docs/RESEARCH_METHODS.md](docs/RESEARCH_METHODS.md).

| Module | Status |
| --- | --- |
| **SonicDNA** — audio analysis, experiences, personal profile | ✅ Working (Phase 1–2) |
| **Resonance Core** — evidence-based learning and insights | ✅ Working (transparent statistics) |
| **Prompt Studio** — Suno prompt packages + feedback loop | ✅ Working (manual Suno workflow) |
| **Provider integrations** — Suno MCP via Claude Code, ElevenLabs API | ✅ Working (Phase 3). ElevenLabs is wire-tested, not yet run against the live API; see [providers](docs/PROVIDER_INTEGRATIONS.md) |
| VisualDNA · Fusion Studio · Resonance Atlas | ⏳ Truthful previews only (Phases 4–6) |

The user interface is in Finnish; code and documentation are in English.

---

## What works today

1. **Analyse music.** Upload MP3/WAV/FLAC/M4A/OGG/AIFF, singly or in batches. Each file is hashed and
   de-duplicated, and its original is kept. It is then analysed in the background, with named stages:
   tempo and tempo ambiguity, beats and onsets, pulse clarity, regularity, syncopation and swing estimates,
   five frequency bands, spectral descriptors, bass-modulation pulse, key and mode with candidates,
   chords, tonal-tension proxy, BS.1770 loudness and loudness range, crest factor, HPSS balance, stereo
   width, texture density, structural segmentation and energy arc.
2. **Explore a track.** A zoomable workspace keeps the waveform, mel spectrogram, band energy, energy,
   local tempo, chroma, chords, tension, structure and your markers in sync with playback. You can click to
   seek, drag to select, and use Ctrl/⌘+wheel to zoom. A *moment inspector* explains what is happening
   at the playhead.
3. **Describe your experience.** Rate 15 optional dimensions (0–10), bodily responses, free-text
   reflections and listening context. You can also mark moments or intervals. Every save is versioned.
4. **Compare pairs.** Answer "which affects you more?" and "which do you enjoy more?" as separate questions.
5. **Discover patterns.** Resonance Core builds a versioned SonicDNA profile using Spearman associations
   with permutation tests, Benjamini–Hochberg FDR and bootstrap CIs. It also runs consistency and contrast
   analysis, analyses where your markers fall against each track's own baseline, runs pairwise sign tests,
   and learns from negative examples. It flags confounded features and suggests experiments that could
   separate them (active learning). Every insight links back to tracks, values and timestamps, and carries
   an evidence level: *Havainto → Alustava hypoteesi → Toistuvasti tuettu*.
6. **Generate Suno prompts.** Prompt Studio produces three different, editable packages: *Deep Resonance*,
   *Emotional Intensification* and *Unknown Territory*. Each has a title, genre/hybrid, style, structure tags,
   exclusions, settings, Finnish evidence and uncertainty notes, and measurable targets. Each field has a
   copy button, plus copy-all, edit, save, duplicate, version comparison, JSON/text export and history.
7. **Close the loop.** Import the song you made in Suno and link it to its prompt. It is re-analysed and
   compared with the prompt's targets (*objective alignment*), and you rate it separately (*subjective
   resonance*). It then becomes part of your profile.
8. **Generate through providers (optional).** Use *Claude Code + Suno MCP* (hand-off brief,
   `/suno-generate` slash command, `scripts/rx` import CLI), or *ElevenLabs Music*, which uses the server-side
   API key, shows the exact request and disclosure, offers a free plan step and an explicit cost consent,
   and imports the result automatically as an experiment. Nothing is ever sent or charged without your
   confirmation.
9. **Own your data.** Everything is local (SQLite + files). You can export everything as JSON, the profile
   as JSON, or ratings and features as CSV.

No feature is mocked. Without data, the app says so instead of inventing a profile.

---

## Quick start

Requirements: **Python 3.11+**, **Node 20+**, **FFmpeg** (`brew install ffmpeg` / `apt install ffmpeg`).

```bash
./scripts/setup.sh      # virtualenv + npm install + frontend build
./scripts/start.sh      # → http://127.0.0.1:8000
```

Development (hot reload, API on :8000, UI on :5173):

```bash
./scripts/dev.sh
```

Tests:

```bash
./scripts/test.sh       # backend tests (synthetic signals + full API workflow) + typecheck/build
./scripts/e2e.sh        # real browser end-to-end workflow (Playwright/Chromium)
```

Optional ElevenLabs: set `ELEVENLABS_API_KEY` in `.env` (see `.env.example`) and restart.
Local CLI for Claude Code workflows: `./scripts/rx --help`.

### First use

**Genre folders and a personal suggestion:** In **Kirjasto**, start with **Metalli**, **Elektroninen**
or **Country**, or create your own genre folder with **Uusi lokero**. Choose the destination when
uploading; existing tracks can be moved with the folder selector on each row. **Luo Suno-kehote**
creates a saved prompt from that folder's analysed tracks and opens a short copy-to-Suno view.
Original genre metadata is preserved. Each track belongs to one folder at a time.

The **Sinulle** card on the home and library pages considers every current analysed track,
including unfiled music. It compares genre groups using all enjoyment ratings, then builds a
creative proposal from tracks rated at least 6/10 for enjoyment. Up to 12 references from up to
three groups keep the proposal focused and prevent a large folder from crowding out other
styles. Affect alone is not treated as enjoyment. The card shows its sources and method;
feedback updates the next proposal. No external generation or payment happens when a prompt is created.

1. **Kirjasto → Tuo musiikkia**: add 6–10 tracks. Include music that strongly affects you, *and*
   music that leaves you indifferent or that you dislike. Contrast is what makes patterns visible.
2. Open each track, listen, and fill in **Kokemuksesi** (skip dimensions that don't apply). Mark strong
   moments on the timeline.
3. Go to **SonicDNA** to read your preliminary profile, its evidence and the suggested comparisons.
4. In **Prompt Studio**, pick sources and an objective, then generate. Copy the fields into Suno's Custom Mode.
5. Create the song in Suno, download it, and use **Tuo Suno-tulos** on the prompt card. Rate your experience.

---

## Repository layout

```
apps/web/            React + TypeScript + Vite + Tailwind UI (Finnish)
services/api/        FastAPI + SQLModel + librosa analysis, Resonance Core, Prompt Engine
  app/services/      ingestion · audio_analysis · resonance_core · prompt_engine
  tests/             synthetic-signal tests + end-to-end API workflow
e2e/                 browser workflow test
scripts/             setup / start / dev / test / e2e
docs/                architecture, brand, research methods, providers, privacy, roadmap
data/                local runtime data (git-ignored)
```

Documentation: [Architecture](docs/ARCHITECTURE.md) · [Brand](docs/BRAND.md) ·
[Research methods](docs/RESEARCH_METHODS.md) · [Providers](docs/PROVIDER_INTEGRATIONS.md) ·
[Privacy](docs/DATA_PRIVACY.md) · [Roadmap](docs/PRODUCT_ROADMAP.md) ·
[Working with Claude Code](docs/CLAUDE_WORKFLOW.md) · [Repository naming](docs/REPOSITORY_RENAME.md)

*Product names (ResonanceX, SonicDNA, VisualDNA, …) are provisional; no trademark or domain availability is assumed.*
