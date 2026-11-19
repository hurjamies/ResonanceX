# Architecture

ResonanceX is a **local-first modular monolith**: one FastAPI process (with a background
analysis thread pool) and one React single-page app. It runs on an ordinary laptop with no GPU and
no external services. In production mode the API serves the built UI from `apps/web/dist` on a
single localhost port.

```
Browser (React, Finnish UI)
   │  /api/*  (JSON, multipart upload, HTTP Range audio)
FastAPI ─┬─ api/            routers: assets · experience · prompts/experiments · system/export
         ├─ services/
         │   ├─ ingestion/       validation, SHA-256 dedup, ffprobe metadata, safe storage
         │   ├─ audio_analysis/  SonicDNA engine (FFmpeg decode → librosa/scipy/pyloudnorm)
         │   ├─ resonance_core/  dataset loading, statistics, profile builder, similarity
         │   └─ prompt_engine/   PromptSpecification → provider compilers; experiment alignment
         ├─ workers/jobs.py  persistent job table + ThreadPoolExecutor (re-queues on restart)
         └─ SQLite (SQLModel)   + data/uploads (originals) + data/analysis (time series, PNG)
```

## Layers and boundaries

| Layer | Location | Contract |
| --- | --- | --- |
| Data ingestion | `services/ingestion` | `MediaAsset` row + original file; never overwrites |
| Feature extraction | `services/audio_analysis/engine.py` | `AnalysisOutput(summary, segments, timeseries, spectrogram_png)` |
| Experience modelling | `api/experience.py`, `models` | `ExperienceRating` (+ immutable `FeedbackSession` history), `ExperienceMarker`, `PairwiseComparison` |
| Resonance Core | `services/resonance_core` | versioned `SonicProfileSnapshot.data` (insights, targets, associations, hypotheses, field) |
| Prompt Engine | `services/prompt_engine` | `PromptSpecification` (provider-neutral) → `compile_suno()` / `compile_elevenlabs_plan()` |
| Provider integration | `prompt_engine/compilers.PROVIDERS` | status registry; no network calls in this version |
| Presentation | `apps/web/src/features/*` | typed API client (`services/api.ts`, `types/api.ts`) |

## Key decisions

* **FFmpeg for decoding** (not only libsndfile), so MP3, M4A/AAC, FLAC, OGG/Opus and AIFF all go through
  one pipeline. Analysis runs on a 22.05 kHz stereo copy, and the original file is never modified.
* **Analysis is persisted and versioned.** `AudioAnalysis` is unique on `(asset_id, algorithm_version)`.
  Bump `ALGORITHM_VERSION` in `engine.py` whenever results would change; the UI then offers re-analysis.
  Large time series (10 Hz features, 2 Hz chroma, waveform peaks) are stored as JSON files, and the mel
  spectrogram as a PNG rendered with a dependency-free encoder.
* **Background jobs without infrastructure.** A DB-backed `AnalysisJob` plus a thread pool. Progress
  is reported as real named stages (`decode → rhythm → spectral → tonality → dynamics → structure →
  render`), never as fake percentages. A failure marks only that asset and job as failed.
* **Profile computed on demand and cached by input hash.** `compute_profile()` hashes analyses,
  ratings, markers and comparisons. A new snapshot (version + 1) is stored only when the inputs change, and
  prompts record the `profile_version` they were built from.
* **Specification ≠ provider output.** The Prompt Engine first builds a structured
  `PromptSpecification` (target features with tolerances and evidence sources, directions, structure,
  negative constraints, hypotheses, evidence refs). Compilers translate it, so adding ElevenLabs or
  another provider only needs a new compiler.
* **Experiment alignment** compares the spec's `target_features` with the generated track's measured
  features, allowing half/double-tempo metrical equivalence. Subjective outcome is computed separately
  from the user's rating.
* **Frontend charts are custom canvas lanes** that share one view window (zustand store) instead of
  separate chart libraries. That keeps every lane perfectly time-aligned and lightweight, with no Plotly
  bundle. Playheads are animated with `requestAnimationFrame` from the single global `<audio>` element,
  so React doesn't re-render per frame. WaveSurfer.js was not needed because waveform peaks are
  precomputed server-side.
* **No LLM dependency.** All insights and prompts are rule-based and statistical. An optional LLM
  narrative layer can later be added on top of the structured evidence (never as a source of measurements).

## Data model (SQLite)

`MediaAsset` · `AnalysisJob` · `AudioAnalysis` · `ExperienceRating` · `FeedbackSession` ·
`ExperienceMarker` · `PairwiseComparison` · `SonicProfileSnapshot` · `GeneratedPrompt` ·
`CreativeExperiment`. The spec's `PromptSpecification` lives inside `GeneratedPrompt.specification`,
and user edits are stored in `GeneratedPrompt.edited` without overwriting `compiled`.

Entities for later phases (`VisualAnalysis`, `FusionProject`, `ProviderConfiguration`, …) are deliberately
**not** created yet. `MediaAsset.kind` already distinguishes audio, image and video.

`SQLModel.metadata.create_all` creates the schema. Before the first schema change that has to
migrate existing user data, introduce Alembic (see roadmap).

## API overview

| Area | Endpoints |
| --- | --- |
| Assets | `GET /api/assets`, `POST /api/assets/upload` (multipart, `rights_confirmed`, optional `prompt_id`), `GET/PATCH/DELETE /api/assets/{id}`, `GET /api/assets/{id}/audio` (Range), `POST …/reanalyze`, `GET …/analysis`, `…/timeseries`, `…/spectrogram.png`, `…/similar` |
| Experience | `GET/PUT /api/assets/{id}/rating`, `GET …/rating/history`, `GET/POST /api/assets/{id}/markers`, `PUT/DELETE /api/markers/{id}`, `GET/POST /api/comparisons`, `DELETE /api/comparisons/{id}` |
| Core | `GET /api/profile`, `GET /api/profile/history`, `GET /api/overview`, `GET /api/vocabulary` |
| Prompts | `GET /api/prompt-options`, `POST /api/prompts/generate`, `GET /api/prompts`, `GET/PATCH/DELETE /api/prompts/{id}`, `POST …/duplicate`, `GET …/export?format=json|text`, `GET …/elevenlabs-plan` |
| Experiments | `GET /api/experiments`, `GET/PATCH /api/experiments/{id}` |
| System | `GET /api/health`, `/api/settings`, `/api/providers`, `/api/export/all.json`, `/api/export/profile.json`, `/api/export/ratings.csv` |

Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`.

## Testing

* `services/api/tests/test_audio_engine.py` checks tempo (±3 %), key and mode, chords, spectral centroid and
  band ratios, LUFS differences, crest factor, stereo width, crescendo detection and decode errors on
  **synthetic signals with known properties** (`tests/signals.py`).
* `services/api/tests/test_workflow.py` runs acceptance workflows A–G through the API, including validation,
  duplicates, failure isolation and persistence across an app restart.
* `services/api/tests/test_prompt_engine.py` covers translation rules, compiler concision and dedup, and the
  stats helpers.
* `e2e/workflow.e2e.mjs` drives the real UI in Chromium, including a mobile viewport overflow check.
