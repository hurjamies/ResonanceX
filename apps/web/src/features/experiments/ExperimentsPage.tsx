import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FlaskConical, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button, CategoryBadge, Empty, PageHeader, Panel, Spinner } from "@/components/ui";
import { api, qk, useAssets } from "@/services/api";
import { StatusPill as GenStatus } from "@/features/prompt-studio/ProviderActions";
import { fmtDate, STAGE_FI } from "@/services/format";
import type { AlignmentRow, Experiment } from "@/types/api";
import { Uploader } from "@/features/library/Uploader";

const STATUS: Record<AlignmentRow["status"], { label: string; cls: string }> = {
  match: { label: "Toteutui", cls: "text-ok" },
  metrical_equivalent: { label: "Metrisesti vastaava", cls: "text-ok" },
  near: { label: "Lähellä", cls: "text-gold" },
  miss: { label: "Poikkesi", cls: "text-danger" },
  unmeasured: { label: "Ei mitattu", cls: "text-faint" },
};
const VERDICT_CLS: Record<string, string> = {
  supports: "border-ok/40 bg-ok/5 text-ok",
  challenges: "border-danger/40 bg-danger/5 text-danger",
  surprise: "border-gold/40 bg-gold/5 text-gold",
  inconclusive: "border-line text-muted",
  mixed: "border-cyan/30 bg-cyan/5 text-cyan",
};
const ARC_FI: Record<string, string> = { plateau: "Tasainen", gradual_build: "Asteittainen nousu", sudden_contrasts: "Äkilliset kontrastit", early_peak: "Varhainen huippu", waves: "Aaltoileva" };

function ExperimentCard({ e }: { e: Experiment }) {
  const qc = useQueryClient();
  const [note, setNote] = useState(e.outcome_note ?? "");
  const save = useMutation({ mutationFn: () => api.patchExperiment(e.id, { outcome_note: note }), onSuccess: () => qc.invalidateQueries({ queryKey: qk.experiments }) });
  const a = e.alignment;
  const o = e.outcome;
  return (
    <Panel
      eyebrow={`Koe #${e.id} · ${fmtDate(e.created_at)}`}
      title={
        <span>
          {e.prompt?.title} <span className="text-muted">→</span>{" "}
          <Link to={`/tracks/${e.asset?.id}`} className="text-gold hover:underline">
            {e.asset?.title}
          </Link>
        </span>
      }
      actions={<span className="rounded-full border border-line px-2 py-0.5 text-2xs text-muted">{e.prompt?.mode_label} · profiili v{e.prompt?.profile_version}</span>}
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-medium">
              1 · Tekninen vastaavuus <CategoryBadge cat="measured" />
            </h3>
            <span className="font-mono text-sm text-cyan">
              {a.matches}/{a.total} {a.score !== null && `(${Math.round(a.score * 100)} %)`}
            </span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-faint">
                <th className="pb-1 font-normal">Piirre</th>
                <th className="pb-1 font-normal">Tavoite</th>
                <th className="pb-1 font-normal">Mitattu</th>
                <th className="pb-1 font-normal">Tulos</th>
              </tr>
            </thead>
            <tbody>
              {a.features.map((r) => (
                <tr key={r.feature} className="border-t border-line/60" title={r.note ?? undefined}>
                  <td className="py-1.5 pr-2 text-muted">{r.label}</td>
                  <td className="py-1.5 pr-2 font-mono tabular">{r.target_label}</td>
                  <td className="py-1.5 pr-2 font-mono tabular">{r.measured_label}</td>
                  <td className={clsx("py-1.5", STATUS[r.status].cls)}>{STATUS[r.status].label}</td>
                </tr>
              ))}
              {a.energy_arc && (
                <tr className="border-t border-line/60">
                  <td className="py-1.5 pr-2 text-muted">Energiakaari</td>
                  <td className="py-1.5 pr-2">{ARC_FI[a.energy_arc.target]}</td>
                  <td className="py-1.5 pr-2">{ARC_FI[a.energy_arc.measured]}</td>
                  <td className={clsx("py-1.5", a.energy_arc.status === "match" ? "text-ok" : "text-danger")}>{a.energy_arc.status === "match" ? "Toteutui" : "Poikkesi"}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-medium">
            2 · Subjektiivinen resonanssi <CategoryBadge cat="self_reported" />
          </h3>
          {!o.rated ? (
            <div className="rounded-lg border border-dashed border-line-strong p-4 text-sm text-muted">
              Kokemusta ei ole vielä arvioitu.{" "}
              <Link to={`/tracks/${e.asset?.id}`} className="text-violet-soft hover:underline">
                Kuuntele ja arvioi tulos →
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="eyebrow">Resonanssi</div>
                <div className="font-display text-2xl text-gold">{o.resonance_score?.toFixed(1) ?? "–"}</div>
              </div>
              <div>
                <div className="eyebrow">Mieltymys</div>
                <div className="font-display text-2xl">{o.preference ?? "–"}</div>
              </div>
              <div>
                <div className="eyebrow">Kirjaston ka.</div>
                <div className="font-display text-2xl text-muted">{o.library_mean_resonance?.toFixed(1) ?? "–"}</div>
              </div>
            </div>
          )}
          <div className={clsx("mt-4 rounded-lg border px-3 py-2 text-sm", VERDICT_CLS[o.verdict ?? "inconclusive"] ?? "border-line text-muted")}>{o.verdict_fi}</div>
          {e.prompt?.hypotheses.length ? (
            <div className="mt-3 text-xs text-muted">
              Testattu hypoteesi: <span className="font-mono text-cyan">{e.prompt.hypotheses[0]}</span>
            </div>
          ) : null}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-2 border-t border-line pt-4">
        <label className="min-w-0 flex-1 text-sm">
          <span className="mb-1 block text-xs text-muted">Muistiinpanot ja jatkokehitys</span>
          <input value={note} onChange={(ev) => setNote(ev.target.value)} placeholder="Mitä opit? Mitä muuttaisit seuraavaan versioon?" className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
        </label>
        <Button size="sm" className="h-9" onClick={() => save.mutate()} loading={save.isPending} disabled={note === (e.outcome_note ?? "")}>
          Tallenna
        </Button>
      </div>
    </Panel>
  );
}

const PROVIDER_FI: Record<string, string> = { elevenlabs: "ElevenLabs" };

function GenerationHistory() {
  const gens = useQuery({
    queryKey: qk.generations,
    queryFn: () => api.generations(),
    refetchInterval: (q) => (q.state.data?.some((g) => g.status === "queued" || g.status === "running") ? 2000 : false),
  });
  if (!gens.data?.length) return null;
  return (
    <Panel eyebrow="Palveluntarjoajat" title={`Generoinnit (${gens.data.length})`}>
      <ul className="flex flex-col gap-2 text-sm">
        {gens.data.slice(0, 12).map((g) => (
          <li key={g.id} className="rounded-lg border border-line px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="truncate">
                #{g.id} · {PROVIDER_FI[g.provider] ?? g.provider} · {g.prompt_title ?? `kehote #${g.prompt_id}`}
              </span>
              <GenStatus job={g} />
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 text-2xs text-faint">
              <span>{g.provider_model}</span>
              <span>arvio ~{g.cost_estimate.amount.toFixed(2)} $</span>
              <span>{fmtDate(g.created_at)}</span>
              {g.result_asset && (
                <Link to={`/tracks/${g.result_asset.id}`} className="text-gold hover:underline">
                  {g.result_asset.title}
                </Link>
              )}
            </div>
            {g.error && <div className="mt-1 text-xs text-danger">{g.error}</div>}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-2xs text-faint">Hyväksyntää odottavat pyynnöt voi vahvistaa tai perua kehotekortin ElevenLabs-ikkunasta. Mitään ei lähetetä uudelleen automaattisesti.</p>
    </Panel>
  );
}

export default function ExperimentsPage() {
  const assets = useAssets();
  const pending = (assets.data ?? []).filter((a) => a.origin === "generated" && a.status !== "completed");
  const analysing = pending.some((a) => a.status !== "failed");
  const exps = useQuery({ queryKey: qk.experiments, queryFn: api.experiments, refetchInterval: analysing ? 2000 : false });
  // when a result finishes analysing, fetch once more so its experiment appears (polling stops at that moment)
  const pendingKey = pending.map((a) => `${a.id}:${a.status}`).join(",");
  const prevKey = useRef(pendingKey);
  const refetchExps = exps.refetch;
  useEffect(() => {
    if (prevKey.current !== pendingKey) refetchExps();
    prevKey.current = pendingKey;
  }, [pendingKey, refetchExps]);
  const prompts = useQuery({ queryKey: qk.prompts, queryFn: api.prompts });
  const [pid, setPid] = useState<number | null>(null);
  const qc = useQueryClient();
  return (
    <div>
      <PageHeader
        eyebrow="Luova palautesilmukka"
        icon={<FlaskConical className="size-3.5" />}
        title="Kokeet"
        description="Kehote → Suno → tulos → analyysi → kokemus. Tekninen vastaavuus ja subjektiivinen resonanssi arvioidaan erikseen: tulos voi vastata tavoitetta mutta jäädä tunteettomaksi – tai poiketa ja silti koskettaa."
      />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex flex-col gap-5">
          {pending.length > 0 && (
            <Panel eyebrow="Analyysissa" title="Tuodut tulokset">
              <ul className="flex flex-col gap-2 text-sm">
                {pending.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3">
                    <Link to={`/tracks/${a.id}`} className="truncate hover:text-violet-soft">{a.title}</Link>
                    {a.status === "failed" ? (
                      <span className="text-xs text-danger">Analyysi epäonnistui: {a.error}</span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-xs text-violet-soft">
                        <Loader2 className="size-3 animate-spin" /> {STAGE_FI[a.job?.stage ?? ""] ?? "Jonossa"}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-2xs text-faint">Koe ilmestyy, kun analyysi on valmis ja tulosta on verrattu kehotteen tavoitteisiin.</p>
            </Panel>
          )}
          {exps.isLoading ? (
            <Spinner />
          ) : !exps.data?.length && !pending.length ? (
            <Panel>
              <Empty title="Ei vielä kokeita" icon={<FlaskConical className="size-7" />}>
                Luo kehote Prompt Studiossa, tee sillä kappale Sunossa ja tuo tulos tänne. Tulos analysoidaan ja sitä verrataan kehotteen mitattaviin tavoitteisiin.
              </Empty>
            </Panel>
          ) : (
            (exps.data ?? []).map((e) => <ExperimentCard key={e.id} e={e} />)
          )}
        </div>
        <div className="flex flex-col gap-5 xl:sticky xl:top-6 xl:self-start">
          <GenerationHistory />
          <Panel eyebrow="Tuo tulos" title="Liitä Suno-kappale kehotteeseen">
            {!prompts.data?.length ? (
              <p className="text-sm text-muted">
                Ei kehotteita. <Link to="/prompt-studio" className="text-violet-soft hover:underline">Luo kehote →</Link>
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                <select value={pid ?? ""} onChange={(e) => setPid(e.target.value ? Number(e.target.value) : null)} aria-label="Kehote" className="h-10 w-full rounded-lg border border-line bg-obsidian px-2 text-sm">
                  <option value="">Valitse kehote…</option>
                  {prompts.data.map((p) => (
                    <option key={p.id} value={p.id}>
                      #{p.id} {p.effective.title} · {p.effective.mode_label}
                    </option>
                  ))}
                </select>
                {pid && <Uploader key={pid} promptId={pid} compact onDone={() => qc.invalidateQueries({ queryKey: qk.experiments })} />}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
