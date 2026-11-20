# Working on ResonanceX with Claude Code

## Orientation (read first)

1. `CLAUDE.md`: non-negotiable rules.
2. `docs/ARCHITECTURE.md`: layers, contracts, API.
3. `docs/RESEARCH_METHODS.md`: what each number means; keep the five categories apart.
4. `docs/PRODUCT_ROADMAP.md`: the current phase and known limitations.

## Environment

```bash
./scripts/setup.sh            # once
./scripts/dev.sh              # API :8000 (reload) + Vite :5173
./scripts/test.sh             # pytest + typecheck/build
./scripts/e2e.sh              # browser workflow (needs Playwright + Chromium)
```

Backend tests run analysis jobs synchronously (`RESONANCEX_SYNCHRONOUS_JOBS=true`) in a temporary data
directory. They never touch `data/`.

## Typical tasks

**Change an analysis algorithm.** Edit `services/api/app/services/audio_analysis/engine.py`, then bump
`ALGORITHM_VERSION`. Add or adjust a synthetic-signal test in `tests/test_audio_engine.py` with a realistic
tolerance, and document the method in `RESEARCH_METHODS.md`. Old analyses stay in the DB, and the UI offers
re-analysis.

**Add a profile feature.** Add it to `flatten_features()` in the engine, register a `FeatureDef` in
`app/schemas/vocabulary.py` (Finnish label, unit, category, low/high phrases), and add English prompt
phrases to `FEATURE_PHRASES` in `prompt_engine/builder.py`. Add a tolerance in `TOLERANCES` if it should
be an experiment target.

**Add a provider.** Implement the `ProviderAdapter` protocol in `app/services/integrations/` and register
it in `registry.py`. API generation goes through `generation.py` (prepare → confirm with cost → run → ingest).
Use only documented endpoints, and test the exact wire format against a local stand-in like
`tests/fake_elevenlabs.py`. Never mark a provider verified without a real success.

**Change the schema.** Edit `app/models`, then from `services/api` run
`.venv/bin/alembic revision --autogenerate -m "describe"`. Review the file (SQLite batch mode) and add a
test that upgrades an existing database.

**Add a UI feature.** Create a page under `apps/web/src/features/<module>/`, add types in `types/api.ts`, a
client function in `services/api.ts`, and the route in `app/App.tsx`. Use the primitives in
`components/ui.tsx` (Panel, Button, EvidenceBadge, CategoryBadge, CopyButton, RatingSlider, Tabs, Modal).
All user-facing text is in Finnish.

## Using the Suno MCP from Claude Code

Run `/suno-generate <prompt-id>` (`.claude/commands/suno-generate.md`). It fetches the brief with
`./scripts/rx prompt <id> --handoff`, checks that the `suno` MCP server is connected, lists its real tools,
confirms the fields and credit use with the user, and imports the downloaded song with `./scripts/rx import`.
Never guess tool names, and never create music without the user's explicit yes.

## Definition of done

* `./scripts/test.sh` passes, and so does `./scripts/e2e.sh` for UI-flow changes.
* No mocked data presented as real, no non-functional controls, and no provider presented as connected when it isn't.
* Docs updated to match the implemented behaviour.
