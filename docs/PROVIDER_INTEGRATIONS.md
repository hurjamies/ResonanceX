# Provider integrations

The core of ResonanceX never requires a paid service. Providers live in
`services/api/app/services/integrations/` (adapter contract in `base.py`, registry in
`registry.py`). Their **status is computed, not declared**: "verified" appears only after a real,
successful request has been recorded.

| Provider | How it works | Status values |
| --- | --- | --- |
| **Suno (manual)** | Copy the prompt package into Suno's Custom Mode | `available` |
| **Suno MCP (Claude Code)** | Claude Code uses the official Suno MCP server; ResonanceX supplies the brief and imports the result | `external` (the connection lives in Claude Code) |
| **ElevenLabs Music** | Server-side API adapter with preview → confirm generation | `not_configured` → `configured` → `verified` |

## Safety model (all providers)

1. **Nothing is sent before an explicit user action.** Preparing a request (`POST /api/generations`)
   only stores what *would* be sent.
2. **Exact disclosure.** The UI shows the exact request body and a plain-language list of what leaves the
   machine. Only musical descriptor text is sent: never audio, ratings, reflections, markers or the profile.
3. **Cost consent.** `POST /api/generations/{id}/confirm` must restate the current estimate
   (`accepted_cost`, tolerance $0.005) and accept the disclosure. Requests above
   `RESONANCEX_MAX_GENERATION_USD` (default $3.00) are refused.
4. **No automatic re-sending.** On restart, queued jobs return to `awaiting_confirmation`. Jobs that were
   running are marked failed, with an instruction to check the provider's history, because the provider may
   have charged.
5. **Secrets stay server-side.** Keys come from environment variables, are held as `SecretStr`, and never
   appear in API responses, the browser or git.

## Suno: manual workflow

Each prompt package maps onto Suno fields (UI labels: *Suno-kenttä*, *Vapaa teksti*,
*Suno voi tulkita epätarkasti*, *Suositus*). These facts came from Suno help-centre search results; the help
centre itself was not reachable from the build sandbox:

* v6 family: **v6-mini, v6, v6-wild** (v6-wild is less predictable; suggested for *Unknown Territory*).
* **Weirdness** ranges Safe → Chaos (≈ 50 % baseline), **Style Influence** Loose → Strong, and on v6 **Variety**
  can rewrite style prompts (set it to 0 to keep tags as written).
* **Exclude Styles** is a Pro/Premier feature. No style-field length limit was confirmed; styles are kept to
  about 450 characters.

## Suno: official MCP via Claude Code

Suno's MCP server is `https://api.suno.com/mcp`. You connect by signing in to Suno; there is no API key. It
works with all plans, and creating music uses your plan's credits. Songs appear in your Suno library. Suno
does **not** publish the server's tool names, and an MCP connection authenticated in Claude Code is not
available to a standalone web app. So ResonanceX deliberately does not call Suno itself. It provides:

* **A hand-off brief**: `GET /api/prompts/{id}/handoff` (UI: *Claude Code + Suno MCP* on a prompt card). It
  lists the fields and targets, plus rules for Claude Code: list the server's tools rather than guessing; check
  credits and get an explicit yes before creating; never upload reference audio; import the result.
* **A project slash command**: `.claude/commands/suno-generate.md` → `/suno-generate <prompt-id>`.
* **A local CLI**: `scripts/rx` (`services/api/app/cli.py`, standard library only, refuses non-local hosts):

```bash
claude mcp add --transport http suno https://api.suno.com/mcp   # once; then /mcp to sign in
./scripts/rx prompts
./scripts/rx prompt 12 --handoff
./scripts/rx import ~/Downloads/song.mp3 --prompt 12 --source suno_mcp --i-have-rights
./scripts/rx experiments
```

Imported files are stored with `source_provider = "suno_mcp"`, analysed, and compared with the prompt's
targets (Kokeet).

References: https://help.suno.com/en/articles/14551425 ·
https://help.suno.com/en/articles/14551361 · https://help.suno.com/en/articles/14486145

## ElevenLabs Music: API adapter

`app/services/integrations/elevenlabs.py` uses only these documented endpoints:

| Call | Endpoint | Notes |
| --- | --- | --- |
| Create plan (optional, explicit) | `POST /v1/music/plan` `{prompt, music_length_ms, model_id}` | Costs no credits (rate limited). Returns a MusicPrompt (v1) or a CompositionPlan (v2/v2.5). |
| Compose | `POST /v1/music?output_format=mp3_44100_128` with `{prompt, music_length_ms, model_id}` **or** `{composition_plan, model_id}` | The response body is the audio. A prompt and a plan cannot be combined. |

* Auth: `xi-api-key` header, sent from the server.
* Models: `music_v2_5` (default, recommended), `music_v2`, and `music_v1` (deprecated, removed 31 Jan 2027).
* The prompt is plain English, at most 4100 characters, compiled from the specification and the user's
  edited fields. Length is 3–600 s; above 5 min, some tiers may refuse.
* **Plans are never fabricated.** A plan returned by `/v1/music/plan` is shown to the user (chunks and
  durations when recognisable) and sent back to compose unchanged. The offline
  `GET /api/prompts/{id}/elevenlabs-plan` export uses the legacy music_v1 *sections* shape for reference
  only and is never sent.
* **Cost estimate**: minutes × `RESONANCEX_ELEVENLABS_USD_PER_MINUTE` (default 0.15, the pay-as-you-go API
  price at build time; verify on the pricing page). In plan mode, minutes come from the plan's chunk
  durations.
* **Errors** are mapped to Finnish messages (401 key, 402 quota, 403 plan, 422 content, 429 rate limit,
  timeout: "check your ElevenLabs history before retrying").
* **Results** are ingested as `origin = "generated"`, `source_provider = "elevenlabs"`, linked to the prompt,
  analysed, and turned into an experiment automatically. Safe response headers (for example `song-id`) are
  kept in `response_meta`.

Setup: put `ELEVENLABS_API_KEY=…` in the server environment or `.env`, then restart. The Music API requires a
paid ElevenLabs subscription.

**Verification status.** The adapter's wire format is verified by tests against a local stand-in server
(`services/api/tests/fake_elevenlabs.py`, tests only): headers, query, body, plan pass-through, error mapping,
cost cap and import. It has **not** been run against the live ElevenLabs API, because `api.elevenlabs.io` was
blocked by the build environment's network policy. The Settings page shows "Varmennettu" only after a real
successful generation on your machine.

Docs: https://elevenlabs.io/docs/api-reference/music/compose ·
https://elevenlabs.io/docs/api-reference/music/create-composition-plan ·
https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans · https://elevenlabs.io/pricing/api

## Adding a provider

Implement the `ProviderAdapter` protocol (`info`, `supports_generation`, `prepare`, `generate`, and
optionally `create_plan`), register it in `registry.py`, and add it to `GENERATION_PROVIDERS` only if it can
generate from the app. Use only documented endpoints, and add wire-format tests against a local stand-in.
