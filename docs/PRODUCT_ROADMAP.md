# Product roadmap and status

Status as of this version (`sonicdna-1.0.0`, `core-1.0.0`).

## Phase 0: Foundation ✅

* Repository audit: `hurjamies/ResonanceX` was empty (no commits, no files). No `vibratex`
  repository was visible to the build session, so nothing needed preserving. See [REPOSITORY_RENAME.md](REPOSITORY_RENAME.md).
* ResonanceX identity, design tokens, logo, module icons, app shell (desktop sidebar, mobile drawer, global player).
* FastAPI + SQLModel/SQLite backend, background job runner, local data directory, scripts.

## Phase 1: Functional SonicDNA MVP ✅

Upload (single and batch), validation, hashing and dedup, metadata, original preservation, playback with
HTTP Range. Real signal analysis: rhythm, spectrum, bands, harmony, dynamics and structure. Synchronised
interactive timeline (waveform, spectrogram, bands, energy, tempo, chroma/chords/tension, structure,
markers) with zoom, selection and seek, plus a moment inspector. Song-level experience feedback with
history. Timeline markers for moments and intervals.

## Phase 2: Resonance Core and Suno Prompt Studio ✅ (first complete milestone)

Multi-track comparison and similarity, a versioned SonicDNA profile, evidence-based insights with levels,
contradictions, hypotheses and active-learning experiments, pairwise comparison, the Resonance Field, and
three Suno prompt modes with heuristic genre/hybrid suggestions. Editable, copyable prompt packages with
history, duplication, version comparison and export. Generated-song import, re-analysis, target-vs-result
alignment, and separate subjective rating that feeds back into the profile.

Acceptance workflows A–G pass via `services/api/tests/test_workflow.py` (API) and `scripts/e2e.sh`
(browser). Workflow E (creating music in Suno) is external by design.

### Known limitations of this milestone

* No ML models: no genre, mood, instrument or vocal tagging and no audio embeddings. Genre suggestions
  are rule-based heuristics.
* Chord estimation covers major/minor triads only. Structure role labels are heuristic.
* Loudness is computed on a 22.05 kHz analysis copy, so it is approximate.
* No lyric generation (it needs an LLM). Vocal prompts provide the structure only.
* The schema is created with `create_all`; there are no Alembic migrations yet.
* Insight texts are rule-based Finnish templates; there is no optional LLM narrative layer yet.

## Phase 3: Provider integrations ⏳ next

1. Document a Claude Code + official Suno MCP workflow. Inspect the tools the connected server actually
   exposes before building anything.
2. Provider adapter interface: `compile`, `settings`, `authenticate`, `generate`, `job_status`, `import`,
   `cost`. Every paid action must be explicit, with the cost shown first.
3. ElevenLabs Music: verify the composition-plan schema against the live API, keep the key server-side,
   and import the output automatically into an experiment.
4. Optional LLM narrative and lyrics layer that receives only structured evidence and is opt-in per request.

## Phase 4: VisualDNA ⏳

Image and video import, deterministic image features (palette, brightness, contrast, saturation, colour
temperature, edge density, composition) and video features (scene cuts, motion, shot length). Visual
experience ratings, optional archetypal interpretations the user can accept or reject, a VisualDNA profile,
and a Visual Prompt Studio.

## Phase 5: Fusion Studio ⏳

An audio-timed storyboard from the structure, energy changes and user markers. Suno Visuals clip prompts
(5–15 s, 16:9 and 9:16; verify current capabilities first), per-scene editing, and audiovisual feedback
(music alone, visuals alone, combined).

## Phase 6: Resonance Atlas ⏳

A cross-modal relationship map with switchable, declared similarity types, item drill-down, preference
evolution across profile versions, and experiment recommendations.

## Technical follow-ups

* Alembic migrations before the first breaking schema change.
* Optional process-pool analysis for very long files and batch speed.
* Optional Essentia / embedding models behind a "model prediction" category, never mixed with measurements.
