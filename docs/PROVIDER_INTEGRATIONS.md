# Provider integrations

The core of ResonanceX never requires a paid service. Providers are listed in
`services/api/app/services/prompt_engine/compilers.py → PROVIDERS` with a truthful status, which is also
shown on the Settings page.

| Provider | Status in this version |
| --- | --- |
| Suno (manual) | **Working.** Prompt packages are copied into Suno's Custom Mode by the user. |
| Suno MCP (Claude Code) | **Not connected to the app.** It can be used separately from Claude Code. |
| ElevenLabs Music | **Not implemented.** An experimental composition-plan JSON export exists. |

## Suno: manual workflow (Phase 1, working)

Each prompt package maps onto Suno fields. The UI labels every field:

| Package field | Where it goes | UI label |
| --- | --- | --- |
| Title | Title field (Custom Mode) | Suno-kenttä |
| Style of Music | Styles field | Suno-kenttä |
| Lyrics / Structure | Lyrics field; `[Section: description]` metatags | Suno voi tulkita epätarkasti |
| Instrumental | Instrumental toggle | Suno-kenttä |
| Exclude | Advanced Options → Exclude (Pro/Premier); otherwise `-term` in Styles | Suno-kenttä |
| Hybrid genre, creative direction | Included in or alongside Styles | Vapaa teksti |
| Model / Weirdness / Style Influence / Variety | Recommendations only | Suositus |

Facts used, from Suno's help-centre search results during the build (the help centre itself could not be
fetched from the build sandbox, so re-verify in the app):

* The v6 family includes **v6-mini, v6 and v6-wild**. v6 is the flagship for Pro and Premier, and v6-wild
  is less predictable and more varied. *Unknown Territory* suggests v6-wild.
* **Weirdness** ranges from Safe to Chaos, with about 50 % as the typical baseline. **Style Influence**
  ranges from Loose to Strong.
* On v6 the **Variety** slider can rewrite style prompts; set it to **0** to keep tags as written. The UI
  recommends this.
* **Exclude Styles** is a Pro/Premier feature.
* No current style-field character limit was confirmed. The compiler keeps styles concise (soft limit about
  450 characters) and reports anything it dropped.

Exact BPM, key and frequency content are *not* guaranteed to be followed. That is why every result
should be imported back and measured.

## Suno: official MCP via Claude Code (Phase 2 of the integration strategy)

```bash
claude mcp add --transport http suno https://api.suno.com/mcp
# then inside Claude Code: /mcp  → authenticate
```

Reference: https://help.suno.com/en/articles/14551425

Rules:

* Inspect the tools the connected server actually exposes before scripting anything. Do not invent tool
  names or REST endpoints.
* A connection authenticated in Claude Code is **not** available to the standalone ResonanceX web app.
* Never spend credits without an explicit user action. Show the operation and any known cost first.
* No scraping or browser automation to get around platform restrictions.

A practical assisted loop: export a prompt (`GET /api/prompts/{id}/export?format=json`), ask Claude Code to
create the song with the Suno MCP tools after explicit confirmation, download the audio, and import it with
`POST /api/assets/upload` (`prompt_id=<id>`, `rights_confirmed=true`).

## Phase 3: optional integration inside the app (not started)

Only after the authentication flows, tool contracts, permissions and product terms are confirmed. The
planned adapter interface is: `compile(spec)`, `settings_schema()`, `authenticate()`, `estimate_cost()`,
`generate()` (always user-triggered), `job_status()`, `import_output()`. Secrets stay server-side and
are configured through environment variables, never sent to the browser.

## ElevenLabs Music (secondary provider, not implemented)

Docs: https://elevenlabs.io/docs/overview/capabilities/music ·
https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans

`GET /api/prompts/{id}/elevenlabs-plan` returns an **experimental, unverified** composition plan
(`positive_global_styles`, `negative_global_styles`, `sections[]` with `section_name`,
`positive_local_styles`, `negative_local_styles`, `duration_ms`, `lines`) derived from the same
`PromptSpecification`. It shows that the specification is provider-neutral. Validate it against the live
API before relying on it.
