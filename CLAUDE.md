# CLAUDE.md: ResonanceX

ResonanceX is a local-first *Personal Resonance Intelligence* app. **SonicDNA** analyses audio,
**Resonance Core** learns evidence-based relationships between measured features and the user's
self-reported experiences, and **Prompt Studio** turns the result into Suno prompts. The loop closes by
importing and re-analysing the generated songs.

## Layout

* `services/api` — FastAPI + SQLModel (SQLite) + librosa/scipy/pyloudnorm. Python venv at `services/api/.venv`.
  * `app/services/audio_analysis/engine.py` — SonicDNA engine (`ALGORITHM_VERSION`)
  * `app/services/resonance_core/core.py` — profile, insights, evidence levels (`CORE_VERSION`)
  * `app/services/prompt_engine/` — `PromptSpecification` → provider compilers; experiment alignment
  * `app/schemas/vocabulary.py` — experience dimensions, markers, the feature registry (Finnish labels)
* `apps/web` — React 19 + TS + Vite + Tailwind v4. Finnish UI. Design tokens in `src/styles.css`.
* `docs/` — architecture, research methods, brand, providers, privacy, roadmap.

## Commands

```bash
./scripts/setup.sh | ./scripts/dev.sh | ./scripts/start.sh
./scripts/test.sh   # pytest (synthetic signals + API workflow A–G) + frontend build
./scripts/e2e.sh    # Playwright browser workflow
```

## Non-negotiable rules

1. **Keep the five knowledge categories apart:** measured, algorithmic estimate, model prediction,
   self-reported, statistical relationship, and interpretation. Label them in the UI (`CategoryBadge`).
2. **Never fabricate.** No fake data, mocked analysis, invented user preferences or decorative empty
   charts. Sparse data is shown honestly, with evidence levels computed by code, never by an LLM.
3. **Correlation ≠ causation.** No claims about soul, unconscious, trauma or mental state.
   Archetypal or spiritual content is interpretive and only offered as optional.
4. **Versioning.** Bump `ALGORITHM_VERSION` / `CORE_VERSION` when results change. Persist, don't overwrite.
5. **Privacy.** Local only. No outbound requests without explicit, informed user action. Secrets stay
   server-side and out of git.
6. **Providers.** Never present an integration as working if it isn't. Never spend credits automatically.
   Never invent API endpoints or MCP tools.
7. **Brand.** ResonanceX (parent), SonicDNA, VisualDNA, Resonance Core, Fusion Studio and Resonance Atlas;
   Prompt Studio is a workspace. Dark, restrained, scientific. Respect reduced motion.
8. **Text.** User-facing text is in Finnish; code, identifiers, docs and generation prompts are in English.
9. Unfinished modules are truthful previews (`components/ModulePreview.tsx`) with no dead controls.

See `docs/CLAUDE_WORKFLOW.md` for task recipes and the definition of done.
