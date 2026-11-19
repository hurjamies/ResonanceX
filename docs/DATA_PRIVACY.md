# Data, privacy and rights

ResonanceX handles intimate self-reports and copyrighted media, so it is private by default.

## Where data lives

| Data | Location |
| --- | --- |
| Original audio files | `data/uploads/<sha[:2]>/<sha256>.<ext>` (never modified) |
| Database (assets, analyses, ratings, history, markers, comparisons, profiles, prompts, experiments) | `data/resonancex.db` (SQLite) |
| Time series and spectrogram images | `data/analysis/<asset_id>/<algorithm_version>/` |

`data/` is git-ignored. Override the location with `RESONANCEX_DATA_DIR`. To back up, copy the
directory. To erase everything, delete it.

## Network behaviour

* The API binds to `127.0.0.1` by default. Do not expose it to a network; it has no authentication.
* The app makes **no outbound requests**: no telemetry, CDN fonts or analytics, and no AI APIs.
* Nothing is sent to Suno or any other service by the app. Prompts leave the machine only when *you*
  copy them. Prompts contain derived musical descriptors, not your reflections or personal profile.
* Future providers will show what is about to leave the app (prompt text, audio, images, annotations or
  profile) and require explicit consent per action. A minimal derived brief is preferred over the full profile.
* Provider secrets, when added, stay in server-side environment variables. They are never sent to the
  browser and never committed (`.env` is git-ignored; see `.env.example`).

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
