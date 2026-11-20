---
description: Create a Suno song from a ResonanceX prompt via the official Suno MCP server, then import it back for analysis
argument-hint: <prompt-id>
---

Create a song in Suno from ResonanceX prompt #$ARGUMENTS and bring the result back into ResonanceX.

1. Check that the ResonanceX app is running (`./scripts/rx prompts`). If it is not, ask the user to start it with `./scripts/start.sh` (Windows: double-click `ResonanceX.bat`).
2. Fetch the hand-off brief: `./scripts/rx prompt $ARGUMENTS --handoff`. Follow its rules exactly.
3. Check that the official `suno` MCP server (https://api.suno.com/mcp) is connected and list the tools it actually exposes. If it is missing, tell the user to run
   `claude mcp add --transport http suno https://api.suno.com/mcp` and authenticate with `/mcp`, then stop. Never guess tool names.
4. Show the user the exact fields you will send and the expected credit use (use the server's credits tool if it has one). Wait for an explicit yes before calling any tool that creates music. Do not upload reference audio.
5. After the song exists, help the user download the audio file to this machine, then run
   `./scripts/rx import "<file>" --prompt $ARGUMENTS --source suno_mcp --i-have-rights`
   only after the user confirms they may use the file for personal analysis.
6. Tell the user to open the track in ResonanceX, listen, and rate the experience. Objective alignment appears under Kokeet (Experiments).
