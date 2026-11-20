# Data, privacy and rights

ResonanceX handles intimate self-reports and copyrighted media, so it is private by default.

## Where data lives

| Data | Location |
| --- | --- |
| Original audio files | `data/uploads/<sha[:2]>/<sha256>.<ext>` (never modified) |
| Database (assets, analyses, ratings, history, markers, comparisons, profiles, prompts, experiments) | `data/resonancex.db` (SQLite) |
| Time series and spectrogram images | `data/analysis/<asset_id>/<algorithm_version>/` |
| Generation requests (exact payload, disclosure, cost estimate, outcome; no secrets) | `generation_job` table |

`data/` is git-ignored. Override the location with `RESONANCEX_DATA_DIR`. To back up, copy the
directory. To erase everything, delete it.

## Network behaviour

* The API binds to `127.0.0.1` by default. Do not expose it to a network; it has no authentication.
* By default the app makes **no outbound requests**: no telemetry, CDN fonts or analytics.
* **ElevenLabs (optional)** is contacted only when you (a) create a free composition plan or (b) confirm a
  generation. Both actions show the exact request first and require you to accept the disclosure;
  generation also requires accepting the cost estimate. Only the English musical description text is sent:
  never audio, ratings, reflections, markers or your profile. The created song is also stored in your
  ElevenLabs history under their terms.
* **Suno** is never contacted by the app. You copy prompts yourself, or Claude Code sends them through your
  own Suno MCP connection after asking you.
* The `rx` CLI talks only to the local app; it refuses non-local hosts.
* Provider secrets (`ELEVENLABS_API_KEY`) are read from the server environment only, held as secret values,
  and never returned by the API, sent to the browser or committed (`.env` is git-ignored).

## Input safety

Uploads are checked against an extension allow-list and probed with ffprobe. Size and duration limits
apply, empty, corrupt or too-short files are rejected, and each file is streamed to a temporary file before
an atomic move. Stored names are content hashes, so user filenames never become paths. Served file paths
are resolved and must stay inside the uploads directory, and the SPA static handler only serves files
inside `apps/web/dist`. API inputs are validated with Pydantic: allowed dimensions, ranges, labels and
lengths.

## Overwrites and deletion

Rating saves append an immutable `FeedbackSession` snapshot. Prompt edits are stored next to the original
compilation, and deleting a prompt that has a linked result is refused. Deleting a track (with
confirmation) removes its file, analyses, ratings, markers, comparisons and experiment link.

## Rights

Before any upload, the user confirms they have the right to use the files for personal analysis. Analysis
works on higher-level characteristics. Prompts avoid artist names and do not reproduce melodies, lyrics or
recordings, and reference audio is never uploaded to generative services. Technical analysis does not grant
permission to reuse copyrighted works commercially.

## Export

Settings → Vienti: full JSON export, SonicDNA profile JSON, and a ratings + features CSV.
