"""Suno providers.

* ``suno`` – manual workflow: the user copies the prompt package into Suno.
* ``suno_mcp`` – Claude Code-assisted workflow through Suno's official MCP server
  (https://api.suno.com/mcp, sign-in based). The authenticated MCP connection lives
  in Claude Code, not in this web app, so ResonanceX produces a hand-off brief and
  the result is imported back with the local ``rx`` CLI. Suno does not publish its
  MCP tool names; the brief tells Claude Code to discover them from the server.
"""

from __future__ import annotations

from typing import Any

from app.models import GeneratedPrompt

SUNO_MCP_URL = "https://api.suno.com/mcp"
SUNO_MCP_DOCS = [
    "https://help.suno.com/en/articles/14551425",
    "https://help.suno.com/en/articles/14551361",
    "https://help.suno.com/en/articles/14486145",
]


class SunoManualProvider:
    id = "suno"
    name = "Suno"

    def supports_generation(self) -> bool:
        return False

    def info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": "manual",
            "configured": True,
            "status": "available",
            "status_fi": "Käytössä – kopioi kentät Sunon Custom Modeen",
            "generation": False,
            "models": [{"id": m, "label": m, "note_fi": ""} for m in ("v6-mini", "v6", "v6-wild")],
            "setup_fi": ["Ei asetuksia. Avaa suno.com/create ja kopioi kehotteen kentät."],
            "notes_fi": "Toimii ilman tunnistautumista. Tuo valmis kappale takaisin kehotekortin Tuo Suno-tulos -toiminnolla.",
            "docs": ["https://suno.com/create"],
        }


class SunoMcpProvider:
    id = "suno_mcp"
    name = "Suno MCP (Claude Code)"

    def supports_generation(self) -> bool:
        return False  # not from the web app – generation happens in Claude Code

    def info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": "assisted",
            "configured": None,  # cannot be known from the web app
            "status": "external",
            "status_fi": "Claude Code -avusteinen – yhteys on Claude Codessa, ei tässä sovelluksessa",
            "generation": False,
            "setup_fi": [
                "Claude Codessa: claude mcp add --transport http suno https://api.suno.com/mcp",
                "Kirjaudu: suorita /mcp Claude Codessa ja hyväksy yhteys Suno-tililläsi (ei API-avainta).",
                "Avaa kehotteen Claude Code -ohje tai suorita /suno-generate <kehotteen numero> tässä repositoriossa.",
            ],
            "notes_fi": "Suno ei julkaise MCP-työkalujen nimiä; Claude Code listaa ne yhteydestä. Musiikin luonti kuluttaa Suno-krediittejä – Claude Code pyytää hyväksyntäsi ennen luontia.",
            "docs": SUNO_MCP_DOCS,
        }

    def handoff(self, prompt: GeneratedPrompt, base_url: str) -> dict[str, Any]:
        eff = dict(prompt.compiled or {})
        eff.update(prompt.edited or {})
        s = eff.get("settings") or {}
        cmd = f'./scripts/rx import "<downloaded-file>" --prompt {prompt.id} --source suno_mcp --i-have-rights'
        md = f"""# ResonanceX → Suno via the Suno MCP server

Prompt **#{prompt.id}** · {eff.get('mode_label', prompt.mode)} · SonicDNA profile v{prompt.profile_version}

## Rules (follow exactly)
1. Use only tools that the connected `suno` MCP server ({SUNO_MCP_URL}) actually lists. Do not guess tool names or parameters. If the server is not connected, stop and tell the user to run `/mcp`.
2. Before creating anything: if the server offers a credits/plan tool, check remaining credits. Show the user the exact fields below and the expected credit use, then wait for an explicit "yes".
3. Create one song unless the user asks for more. Never upload reference audio from the ResonanceX library.
4. Use the fields as written (the user may have edited them). Map them to the closest parameters the tool offers; tell the user about anything the tool cannot take (e.g. exclusions or model choice).
5. When the song exists, help the user get the audio file onto this machine (download from their Suno library if no tool returns a file), then import it:

```bash
{cmd}
```

The import links the song to prompt #{prompt.id}; ResonanceX then analyses it and compares it with the targets. Ask the user to rate the experience in the app afterwards.

## Fields
- **Title:** {eff.get('title')}
- **Styles:** {eff.get('style')}
- **Instrumental:** {"yes" if eff.get('instrumental') else "no – " + str(eff.get('vocal'))}
- **Exclude:** {eff.get('exclude') or '-'}
- **Suggested model / settings:** {s.get('model', 'v6')} · weirdness {s.get('weirdness', '-')}% · style influence {s.get('style_influence', '-')}% (only if the tool supports them)

**Lyrics / structure:**
```
{eff.get('lyrics') or ''}
```

## Measurable targets ResonanceX will check afterwards
""" + "\n".join(
            f"- {t['label']}: {t['target']} ± {t['tolerance']}" for t in (prompt.specification or {}).get("target_features", [])
        ) + f"""

_ResonanceX app: {base_url} · fetch this brief again with `./scripts/rx prompt {prompt.id} --handoff`_
"""
        return {"prompt_id": prompt.id, "markdown": md, "import_command": cmd, "slash_command": f"/suno-generate {prompt.id}"}
