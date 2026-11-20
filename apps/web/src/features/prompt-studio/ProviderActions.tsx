import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, Sparkles, Terminal, XCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, CopyButton, ErrorNote, Modal, Spinner } from "@/components/ui";
import { api, qk, useInvalidateDerived, useProviders } from "@/services/api";
import { fmtTime } from "@/services/format";
import type { GenerationJob, PromptRecord } from "@/types/api";

const STATUS_FI: Record<GenerationJob["status"], string> = {
  awaiting_confirmation: "Odottaa vahvistusta",
  queued: "Jonossa",
  running: "Generoidaan ElevenLabsissa…",
  completed: "Valmis – tuotu ja analysoidaan",
  failed: "Epäonnistui",
  cancelled: "Peruttu",
};

/** Provider entry points shown on a prompt card. */
export function ProviderActions({ prompt }: { prompt: PromptRecord }) {
  const [handoff, setHandoff] = useState(false);
  const [el, setEl] = useState(false);
  const providers = useProviders();
  const elInfo = providers.data?.find((p) => p.id === "elevenlabs");
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-obsidian/40 px-3 py-2">
      <span className="eyebrow mr-1">Luo palvelussa</span>
      <a href={prompt.effective.suno_url} target="_blank" rel="noreferrer noopener">
        <Button size="sm" variant="ghost">
          Suno (käsin) <ExternalLink className="size-3.5" />
        </Button>
      </a>
      <Button size="sm" variant="ghost" onClick={() => setHandoff(true)}>
        <Terminal className="size-3.5" /> Claude Code + Suno MCP
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setEl(true)}>
        <Sparkles className="size-3.5" /> ElevenLabs
        <span className={clsx("ml-1 size-1.5 rounded-full", elInfo?.configured ? "bg-ok" : "bg-faint")} title={elInfo?.status_fi} />
      </Button>
      <Modal open={handoff} onClose={() => setHandoff(false)} title={`Claude Code + Suno MCP · kehote #${prompt.id}`} wide>
        <HandoffPanel promptId={prompt.id} />
      </Modal>
      <Modal open={el} onClose={() => setEl(false)} title={`ElevenLabs Music · kehote #${prompt.id}`} wide>
        <ElevenLabsPanel prompt={prompt} />
      </Modal>
    </div>
  );
}

function HandoffPanel({ promptId }: { promptId: number }) {
  const h = useQuery({ queryKey: ["handoff", promptId], queryFn: () => api.handoff(promptId) });
  const providers = useProviders();
  const info = providers.data?.find((p) => p.id === "suno_mcp");
  if (h.isLoading) return <Spinner />;
  if (!h.data) return <ErrorNote error={h.error} />;
  return (
    <div className="flex flex-col gap-5 text-sm">
      <div className="rounded-lg border border-gold/30 bg-gold/5 px-3 py-2 text-xs text-gold">
        Sunon virallinen MCP-yhteys toimii Claude Codessa – ei tässä selainsovelluksessa. ResonanceX ei näe Suno-tiliäsi eikä käytä krediittejäsi. Claude Code kysyy hyväksyntäsi ennen musiikin luontia.
      </div>
      <ol className="flex flex-col gap-3">
        {(info?.setup_fi ?? []).map((step, i) => (
          <li key={i} className="flex gap-3">
            <span className="grid size-6 shrink-0 place-items-center rounded-full border border-violet/40 font-mono text-xs text-violet-soft">{i + 1}</span>
            <span className="pt-0.5 text-muted">{step}</span>
          </li>
        ))}
      </ol>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="eyebrow">Claude Code -komento tässä repositoriossa</span>
          <CopyButton text={h.data.slash_command} />
        </div>
        <pre className="rounded-lg bg-obsidian px-3 py-2 font-mono text-[12.5px] text-cyan">{h.data.slash_command}</pre>
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="eyebrow">Ohje Claude Codelle (englanniksi)</span>
          <CopyButton text={h.data.markdown} label="Kopioi ohje" />
        </div>
        <pre className="max-h-72 overflow-auto rounded-lg bg-obsidian px-3 py-2 font-mono text-[12px] whitespace-pre-wrap text-muted">{h.data.markdown}</pre>
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="eyebrow">Tuloksen tuonti komentoriviltä</span>
          <CopyButton text={h.data.import_command} />
        </div>
        <pre className="overflow-x-auto rounded-lg bg-obsidian px-3 py-2 font-mono text-[12px] text-ink">{h.data.import_command}</pre>
        <p className="mt-1 text-2xs text-faint">Tai tuo ladattu tiedosto kehotekortin Tuo Suno-tulos -painikkeella.</p>
      </div>
    </div>
  );
}

function ElevenLabsPanel({ prompt }: { prompt: PromptRecord }) {
  const providers = useProviders();
  const info = providers.data?.find((p) => p.id === "elevenlabs");
  const qc = useQueryClient();
  const inv = useInvalidateDerived();
  const specDuration = (prompt.specification as { target_duration_seconds?: number | null }).target_duration_seconds;
  const [model, setModel] = useState<string>("");
  const [seconds, setSeconds] = useState<number>(specDuration ?? 180);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [okDisclosure, setOkDisclosure] = useState(false);
  const [okCost, setOkCost] = useState(false);

  const refresh = (j: GenerationJob) => {
    setJob(j);
    qc.invalidateQueries({ queryKey: qk.generations });
    qc.invalidateQueries({ queryKey: qk.providers });
  };
  const prepare = useMutation({
    mutationFn: () => api.prepareGeneration({ prompt_id: prompt.id, provider: "elevenlabs", model_id: model || info?.default_model, duration_seconds: seconds }),
    onSuccess: (j) => {
      setOkCost(false);
      setOkDisclosure(false);
      refresh(j);
    },
  });
  const plan = useMutation({ mutationFn: () => api.planGeneration(job!.id, okDisclosure), onSuccess: (j) => { setOkCost(false); refresh(j); } });
  const confirm = useMutation({
    mutationFn: () => api.confirmGeneration(job!.id, job!.cost_estimate.amount, okDisclosure),
    onSuccess: (j) => {
      refresh(j);
      inv();
    },
  });
  const cancel = useMutation({ mutationFn: () => api.cancelGeneration(job!.id), onSuccess: refresh });
  // poll while in flight
  useQuery({
    queryKey: ["generation", job?.id],
    queryFn: async () => {
      const j = await api.generation(job!.id);
      if (j.status !== job!.status) {
        refresh(j);
        if (j.status === "completed") inv();
      }
      return j;
    },
    enabled: !!job && (job.status === "queued" || job.status === "running"),
    refetchInterval: 1500,
  });

  if (!info) return <Spinner />;
  const est = job?.cost_estimate;
  const planChunks = job?.request.mode === "plan" ? planSummary(job.request.body.composition_plan) : null;
  const editable = !job || job.status === "awaiting_confirmation";

  return (
    <div className="flex flex-col gap-5 text-sm">
      {!info.configured && (
        <div className="rounded-lg border border-line-strong bg-surface/40 p-3">
          <div className="mb-1 font-medium text-ink">ElevenLabsia ei ole määritetty</div>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-muted">
            {info.setup_fi.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-faint">Voit silti esikatsella täsmälleen, mitä lähetettäisiin ja mitä se maksaisi.</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-[1fr_160px_auto] sm:items-end">
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Malli</span>
          <select value={model || info.default_model} onChange={(e) => setModel(e.target.value)} disabled={!editable} className="h-9 w-full rounded-lg border border-line bg-obsidian px-2 text-sm">
            {(info.models ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
                {m.note_fi ? ` – ${m.note_fi}` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Kesto (s)</span>
          <input type="number" min={3} max={600} value={seconds} disabled={!editable} onChange={(e) => setSeconds(Number(e.target.value))} className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm" />
        </label>
        <Button onClick={() => prepare.mutate()} loading={prepare.isPending} disabled={!editable || !(seconds >= 3 && seconds <= 600)}>
          {job ? "Valmistele uudelleen" : "Valmistele pyyntö"}
        </Button>
      </div>
      <p className="-mt-3 text-2xs text-faint">Valmistelu ei lähetä mitään. Pyyntö tallennetaan historiaan odottamaan vahvistustasi.</p>
      <ErrorNote error={prepare.error} />

      {job && est && (
        <div className="flex flex-col gap-4 rounded-xl border border-line p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Pyyntö #{job.id} · {job.provider_model} · {job.request.mode === "plan" ? "sävellyssuunnitelma" : "kehote"}</span>
            <StatusPill job={job} />
          </div>
          {(job.response_meta.warnings ?? []).map((w) => (
            <div key={w} className="flex items-start gap-2 text-xs text-gold">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> {w}
            </div>
          ))}
          {job.response_meta.requeued_note && <div className="text-xs text-gold">{job.response_meta.requeued_note}</div>}

          <div>
            <div className="eyebrow mb-1.5">Mitä lähtee koneeltasi</div>
            <ul className="flex flex-col gap-1 text-xs text-muted">
              {job.disclosure.map((d) => (
                <li key={d} className="flex gap-2">
                  <span className="text-cyan">→</span>
                  {d}
                </li>
              ))}
            </ul>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-violet-soft select-none">Näytä täsmällinen pyyntö ({job.request.endpoint})</summary>
              <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-obsidian p-3 font-mono text-[11.5px] whitespace-pre-wrap text-muted">
                {JSON.stringify({ query: job.request.query, body: job.request.body }, null, 2)}
              </pre>
            </details>
          </div>

          {planChunks && (
            <div>
              <div className="eyebrow mb-1.5">ElevenLabsin luoma sävellyssuunnitelma (lähetetään sellaisenaan)</div>
              <ul className="flex flex-col gap-1 text-xs">
                {planChunks.map((c, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="w-12 shrink-0 font-mono text-cyan">{c.duration ? fmtTime(c.duration / 1000) : "–"}</span>
                    <span className="text-muted">{c.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center">
            <div className={clsx("font-display text-3xl tabular", est.exceeds_cap ? "text-danger" : "text-gold")}>~{est.amount.toFixed(2)} $</div>
            <div className="text-xs text-muted">
              {est.minutes.toFixed(2)} min × {est.rate_per_minute.toFixed(2)} $/min · {est.basis_fi}. {est.note_fi}
              {est.exceeds_cap && <div className="mt-1 text-danger">Ylittää pyyntökohtaisen rajan {est.cap.toFixed(2)} $ – lyhennä kestoa tai nosta rajaa (RESONANCEX_MAX_GENERATION_USD).</div>}
            </div>
          </div>

          {job.status === "awaiting_confirmation" && (
            <>
              <label className="flex items-start gap-2 text-xs text-muted">
                <input type="checkbox" checked={okDisclosure} onChange={(e) => setOkDisclosure(e.target.checked)} className="mt-0.5 accent-violet" />
                Ymmärrän, mitä tietoja lähetetään ElevenLabsille.
              </label>
              {info.configured && job.request.mode === "prompt" && (
                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="ghost" disabled={!okDisclosure} loading={plan.isPending} onClick={() => plan.mutate()}>
                    Luo maksuton sävellyssuunnitelma
                  </Button>
                  <span className="text-2xs text-faint">Valinnainen. Lähettää kehotetekstin ElevenLabsille; ei maksa krediittejä. Voit tarkistaa osat ennen generointia.</span>
                </div>
              )}
              <ErrorNote error={plan.error} />
              <label className="flex items-start gap-2 text-xs text-muted">
                <input type="checkbox" checked={okCost} onChange={(e) => setOkCost(e.target.checked)} disabled={est.exceeds_cap} className="mt-0.5 accent-violet" />
                Hyväksyn arvioidun kustannuksen noin {est.amount.toFixed(2)} $ ElevenLabs-tililleni.
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="primary" disabled={!info.configured || !okDisclosure || !okCost || est.exceeds_cap} loading={confirm.isPending} onClick={() => confirm.mutate()}>
                  Generoi ElevenLabsilla
                </Button>
                <Button variant="ghost" onClick={() => cancel.mutate()} loading={cancel.isPending}>
                  Peru pyyntö
                </Button>
                {!info.configured && <span className="text-xs text-faint">Generointi vaatii API-avaimen palvelimelle.</span>}
              </div>
              <ErrorNote error={confirm.error ?? cancel.error} />
            </>
          )}

          {(job.status === "queued" || job.status === "running") && (
            <div className="flex items-center gap-2 text-sm text-violet-soft">
              <Loader2 className="size-4 animate-spin" /> {STATUS_FI[job.status]} Generointi voi kestää useita minuutteja; voit sulkea ikkunan.
            </div>
          )}
          {job.status === "completed" && (
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <CheckCircle2 className="size-4 text-ok" />
              <span>Kappale tuotiin ja liitettiin kehotteeseen.</span>
              {job.result_asset_id && (
                <Link to={`/tracks/${job.result_asset_id}`} className="text-gold hover:underline">
                  Kuuntele ja arvioi →
                </Link>
              )}
              <Link to="/experiments" className="text-violet-soft hover:underline">
                Kokeet →
              </Link>
            </div>
          )}
          {job.status === "failed" && (
            <div className="flex items-start gap-2 text-sm text-danger">
              <XCircle className="mt-0.5 size-4 shrink-0" />
              <span>{job.error}</span>
            </div>
          )}
        </div>
      )}
      <p className="text-2xs text-faint">
        {info.notes_fi} {info.cost?.basis_fi}
      </p>
    </div>
  );
}

export function StatusPill({ job }: { job: GenerationJob }) {
  const cls = {
    awaiting_confirmation: "bg-gold/10 text-gold",
    queued: "bg-violet/10 text-violet-soft",
    running: "bg-violet/10 text-violet-soft",
    completed: "bg-ok/10 text-ok",
    failed: "bg-danger/10 text-danger",
    cancelled: "bg-surface text-muted",
  }[job.status];
  return <span className={clsx("rounded-full px-2 py-0.5 text-2xs", cls)}>{STATUS_FI[job.status]}</span>;
}

/** Summarise a provider-returned plan without assuming more than its visible structure. */
function planSummary(plan: unknown): { label: string; duration: number | null }[] | null {
  const items = Array.isArray(plan)
    ? plan
    : plan && typeof plan === "object"
      ? ((plan as Record<string, unknown>).chunks ?? (plan as Record<string, unknown>).sections)
      : null;
  if (!Array.isArray(items)) return null;
  return items.map((it) => {
    const o = (it ?? {}) as Record<string, unknown>;
    const label = String(o.text ?? o.section_name ?? "").split("\n")[0].slice(0, 80) || "–";
    const styles = (o.positive_styles ?? o.positive_local_styles) as string[] | undefined;
    const d = (o.duration_ms ?? o.durationMs) as number | undefined;
    return { label: styles?.length ? `${label} · ${styles.slice(0, 3).join(", ")}` : label, duration: typeof d === "number" ? d : null };
  });
}
