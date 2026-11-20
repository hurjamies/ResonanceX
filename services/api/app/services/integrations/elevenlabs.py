"""ElevenLabs Music adapter.

Only documented endpoints are used (elevenlabs.io/docs/api-reference/music):

* ``POST /v1/music/plan`` – create a composition plan from a prompt. Costs no credits
  (rate limited by tier). Returns a MusicPrompt (music_v1) or CompositionPlan
  (music_v2, music_v2_5).
* ``POST /v1/music`` – compose. Body takes *either* ``prompt`` (+ optional
  ``music_length_ms`` 3000–600000) *or* ``composition_plan``, plus ``model_id``.
  ``output_format`` is a query parameter (codec_sample_rate_bitrate). The response
  body is the audio stream.

Authentication: ``xi-api-key`` header, sent from this server only.

A plan returned by ``/v1/music/plan`` is passed back to compose unchanged, so the
app never has to fabricate the provider's plan schema.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.models import GeneratedPrompt
from app.services.integrations.base import GenerationResult, PreparedRequest, ProviderError

DOCS = [
    "https://elevenlabs.io/docs/api-reference/music/compose",
    "https://elevenlabs.io/docs/api-reference/music/create-composition-plan",
    "https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans",
    "https://elevenlabs.io/pricing/api",
]

MODELS = [
    {"id": "music_v2_5", "label": "Music v2.5", "note_fi": "ElevenLabsin suosittelema malli."},
    {"id": "music_v2", "label": "Music v2", "note_fi": ""},
    {"id": "music_v1", "label": "Music v1", "note_fi": "Vanhentuva – ElevenLabs poistaa mallin 31.1.2027."},
]
MODEL_IDS = {m["id"] for m in MODELS}
DEFAULT_MODEL = "music_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"
PROMPT_MAX_CHARS = 4100
MIN_MS, MAX_MS = 3_000, 600_000
DEFAULT_SECONDS = 180
SAFE_RESPONSE_HEADERS = ("content-type", "content-length", "song-id", "request-id", "x-request-id", "history-item-id")


def compile_prompt(prompt: GeneratedPrompt) -> str:
    """Natural-language music prompt (English) from the specification and the user's
    effective (possibly edited) prompt package. Contains only musical descriptors."""
    spec = prompt.specification or {}
    eff = dict(prompt.compiled or {})
    eff.update(prompt.edited or {})
    lines: list[str] = []
    genre = eff.get("hybrid_genre") or eff.get("primary_genre")
    if genre:
        lines.append(f"An original {genre} piece.")
    if eff.get("style"):
        lines.append(f"Style: {eff['style']}.")
    structure = spec.get("structure") or []
    if structure:
        parts = []
        for s in structure:
            secs = s.get("approx_seconds")
            parts.append(f"{s['tag']} ({int(secs)} s): {s['description']}" if secs else f"{s['tag']}: {s['description']}")
        lines.append("Structure: " + "; ".join(parts) + ".")
    vocal = spec.get("vocal_direction") or eff.get("vocal") or "instrumental"
    lines.append("Instrumental only, no vocals." if vocal == "instrumental" else f"Vocals: {vocal}.")
    if eff.get("exclude"):
        lines.append(f"Avoid: {eff['exclude']}.")
    if eff.get("creative_direction"):
        lines.append(str(eff["creative_direction"]))
    lines.append("Do not imitate any existing song or artist.")
    text = " ".join(lines)
    return text[:PROMPT_MAX_CHARS]


def plan_duration_ms(plan: Any) -> int | None:
    """Sum durations of a provider-returned plan if its structure exposes them.

    Supports the documented chunk plan (music_v2/2.5: items with ``duration_ms``) and
    the sections plan (music_v1). Returns None when the structure is unrecognised –
    the caller then falls back to the requested length and says so."""

    def items(obj: Any) -> list[Any]:
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("chunks", "sections"):
                if isinstance(obj.get(key), list):
                    return obj[key]
        return []

    total = 0
    found = False
    for it in items(plan):
        if isinstance(it, dict):
            d = it.get("duration_ms", it.get("durationMs"))
            if isinstance(d, (int, float)):
                total += int(d)
                found = True
    return total if found else None


class ElevenLabsAdapter:
    id = "elevenlabs"
    name = "ElevenLabs Music"

    # ------------------------------------------------------------------ status
    def configured(self) -> bool:
        key = get_settings().elevenlabs_api_key
        return bool(key and key.get_secret_value().strip())

    def supports_generation(self) -> bool:
        return True

    def info(self) -> dict[str, Any]:
        s = get_settings()
        configured = self.configured()
        return {
            "id": self.id,
            "name": self.name,
            "kind": "api",
            "configured": configured,
            "status": "configured" if configured else "not_configured",
            "status_fi": "API-avain asetettu palvelimelle" if configured else "Ei määritetty – API-avainta ei ole asetettu",
            "generation": configured,
            "models": MODELS,
            "default_model": DEFAULT_MODEL,
            "cost": {
                "usd_per_minute": s.elevenlabs_usd_per_minute,
                "max_per_request_usd": s.max_generation_usd,
                "basis_fi": f"Arvio {s.elevenlabs_usd_per_minute:.2f} $/min (ElevenLabsin API-hinnasto rakennushetkellä). Sävellyssuunnitelma on maksuton. Tarkista ajantasainen hinta.",
            },
            "setup_fi": [
                "Luo API-avain ElevenLabsin kehittäjäasetuksissa (Music API vaatii maksullisen tilauksen).",
                "Aseta avain palvelimen ympäristömuuttujaan ELEVENLABS_API_KEY (tai .env-tiedostoon) ja käynnistä ResonanceX uudelleen.",
                "Avain ei koskaan päädy selaimeen eikä versionhallintaan.",
            ],
            "notes_fi": "Generointi käynnistyy vain, kun olet hyväksynyt täsmällisen pyynnön, lähetettävät tiedot ja kustannusarvion. Tulos tuodaan automaattisesti kokeeksi.",
            "docs": DOCS,
        }

    # ----------------------------------------------------------------- prepare
    def prepare(self, prompt: GeneratedPrompt, options: dict[str, Any]) -> PreparedRequest:
        s = get_settings()
        model = options.get("model_id") or DEFAULT_MODEL
        if model not in MODEL_IDS:
            raise ProviderError(f"Tuntematon malli: {model}")
        seconds = options.get("duration_seconds") or (prompt.specification or {}).get("target_duration_seconds") or DEFAULT_SECONDS
        length_ms = int(max(MIN_MS, min(MAX_MS, round(float(seconds) * 1000))))
        text = compile_prompt(prompt)
        warnings = []
        if model == "music_v1":
            warnings.append("music_v1 on vanhentuva ja poistuu 31.1.2027 – suosittelemme mallia music_v2_5.")
        if length_ms > 300_000:
            warnings.append("Yli 5 minuutin pituus ei välttämättä ole sallittu kaikilla tilauksilla.")
        request = {
            "endpoint": "POST /v1/music",
            "query": {"output_format": OUTPUT_FORMAT},
            "body": {"prompt": text, "music_length_ms": length_ms, "model_id": model},
            "mode": "prompt",
        }
        return PreparedRequest(
            request=request,
            disclosure=self._disclosure(len(text)),
            cost_estimate=self.estimate(length_ms, basis="requested_length"),
            provider_model=model,
            warnings=warnings,
        )

    def _disclosure(self, n_chars: int) -> list[str]:
        return [
            f"Englanninkielinen musiikillinen kuvaus ({n_chars} merkkiä) lähetetään ElevenLabsille (api.elevenlabs.io).",
            "Ei lähetetä: äänitiedostoja, arvioitasi, pohdintojasi, hetkimerkintöjä eikä SonicDNA-profiiliasi.",
            "API-avain lähetetään ResonanceX-palvelimelta xi-api-key-otsakkeessa – ei selaimesta.",
            "Luotu kappale tallentuu myös ElevenLabs-tilisi historiaan heidän ehtojensa mukaisesti.",
        ]

    def estimate(self, length_ms: int, *, basis: str) -> dict[str, Any]:
        s = get_settings()
        minutes = length_ms / 60_000
        usd = round(minutes * s.elevenlabs_usd_per_minute, 4)
        return {
            "currency": "USD",
            "amount": usd,
            "minutes": round(minutes, 3),
            "rate_per_minute": s.elevenlabs_usd_per_minute,
            "basis": basis,
            "basis_fi": {
                "requested_length": "Pyydetty kesto × hinnaston minuuttihinta",
                "plan_length": "Sävellyssuunnitelman osien kestojen summa × minuuttihinta",
                "plan_unknown_length": "Suunnitelman kestoa ei voitu lukea – arvio pyydetyn keston mukaan",
            }[basis],
            "exceeds_cap": usd > s.max_generation_usd,
            "cap": s.max_generation_usd,
            "note_fi": "Arvio. Lopullinen veloitus määräytyy ElevenLabsin hinnaston ja tilauksesi mukaan.",
        }

    # ------------------------------------------------------------- http calls
    def _client(self) -> httpx.Client:
        s = get_settings()
        if not self.configured():
            raise ProviderError("ElevenLabs-API-avainta ei ole asetettu palvelimelle.", status=None)
        return httpx.Client(
            base_url=s.elevenlabs_base_url.rstrip("/"),
            headers={"xi-api-key": s.elevenlabs_api_key.get_secret_value().strip()},  # type: ignore[union-attr]
            timeout=httpx.Timeout(connect=15.0, read=s.generation_timeout_seconds, write=30.0, pool=15.0),
        )

    @staticmethod
    def _raise_for(resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        detail = resp.text[:500]
        msg = {
            401: "ElevenLabs hylkäsi API-avaimen (401).",
            402: "ElevenLabs: maksu tai kiintiö ei riitä (402).",
            403: "ElevenLabs: ei oikeutta tähän toimintoon – Music API vaatii maksullisen tilauksen (403).",
            422: "ElevenLabs hylkäsi pyynnön sisällön (422).",
            429: "ElevenLabsin käyttöraja täyttyi – yritä myöhemmin (429).",
        }.get(resp.status_code, f"ElevenLabs palautti virheen {resp.status_code}.")
        raise ProviderError(msg, status=resp.status_code, detail=detail, retryable=resp.status_code in (429, 500, 502, 503, 504))

    def create_plan(self, request: dict[str, Any]) -> dict[str, Any]:
        """Free plan creation from the prepared prompt; returns the provider's plan as-is."""
        body = request.get("body") or {}
        if "prompt" not in body:
            raise ProviderError("Suunnitelma voidaan luoda vain kehotepohjaisesta pyynnöstä.")
        payload = {"prompt": body["prompt"], "music_length_ms": body.get("music_length_ms"), "model_id": body.get("model_id", DEFAULT_MODEL)}
        try:
            with self._client() as c:
                resp = c.post("/v1/music/plan", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Yhteys ElevenLabsiin epäonnistui: {exc.__class__.__name__}", retryable=True) from exc
        self._raise_for(resp)
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError("ElevenLabs palautti suunnitelman odottamattomassa muodossa.") from exc

    def request_with_plan(self, request: dict[str, Any], plan: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """Switch a prepared request to plan mode (prompt and length are not sent with a plan)."""
        body = request["body"]
        new = {
            "endpoint": "POST /v1/music",
            "query": request.get("query", {"output_format": OUTPUT_FORMAT}),
            "body": {"composition_plan": plan, "model_id": body.get("model_id", DEFAULT_MODEL)},
            "mode": "plan",
            "source_prompt": body.get("prompt") or request.get("source_prompt"),
            "requested_length_ms": body.get("music_length_ms") or request.get("requested_length_ms"),
        }
        total = plan_duration_ms(plan)
        if total:
            cost = self.estimate(total, basis="plan_length")
        else:
            cost = self.estimate(int(new["requested_length_ms"] or DEFAULT_SECONDS * 1000), basis="plan_unknown_length")
        return new, cost

    def generate(self, request: dict[str, Any]) -> GenerationResult:
        body = request.get("body") or {}
        if not ("prompt" in body) ^ ("composition_plan" in body):
            raise ProviderError("Pyynnössä on oltava joko kehote tai sävellyssuunnitelma (ei molempia).")
        try:
            with self._client() as c:
                resp = c.post("/v1/music", params=request.get("query") or {"output_format": OUTPUT_FORMAT}, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "ElevenLabs ei vastannut aikarajan sisällä. Tarkista ElevenLabs-historiastasi, syntyikö kappale, ennen kuin yrität uudelleen.",
                retryable=False,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Yhteys ElevenLabsiin epäonnistui: {exc.__class__.__name__}", retryable=True) from exc
        self._raise_for(resp)
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if not (ctype.startswith("audio/") or ctype == "application/octet-stream"):
            raise ProviderError("ElevenLabs palautti odottamattoman vastauksen (ei äänidataa).", detail=resp.text[:300])
        if len(resp.content) < 1024:
            raise ProviderError("ElevenLabs palautti tyhjän tai liian lyhyen äänitiedoston.")
        meta = {k: resp.headers[k] for k in SAFE_RESPONSE_HEADERS if k in resp.headers}
        meta["bytes"] = len(resp.content)
        fmt = str((request.get("query") or {}).get("output_format", OUTPUT_FORMAT))
        ext = ".mp3" if fmt.startswith("mp3") or ctype == "audio/mpeg" else (".wav" if "wav" in ctype or fmt.startswith("pcm") else ".mp3")
        return GenerationResult(audio=resp.content, content_type=ctype, file_extension=ext, meta=meta)
