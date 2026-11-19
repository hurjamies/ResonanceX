import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Search, Sparkles, Wand2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, Chip, Empty, ErrorNote, EvidenceBadge, PageHeader, Panel, Spinner, Tabs } from "@/components/ui";
import { PromptIcon } from "@/design-system/brand";
import { api, qk, useAssets, useProfile } from "@/services/api";
import { fmtDate } from "@/services/format";
import type { PromptRecord } from "@/types/api";
import { PromptCard } from "./PromptCard";

type Controls = {
  genre: string;
  target_bpm: number | null;
  rhythmic_intensity: number | null;
  bass_emphasis: number | null;
  harmonic_darkness: number | null;
  melancholy: number | null;
  euphoria: number | null;
  hypnotic_repetition: number | null;
  tension: number | null;
  texture_density: number | null;
  vocal: string;
  experimentation: number | null;
  duration_seconds: number | null;
  extra_exclude: string;
};

const SLIDERS: { key: keyof Controls; label: string; profileFeature?: string }[] = [
  { key: "rhythmic_intensity", label: "Rytminen intensiteetti", profileFeature: "beat_strength" },
  { key: "bass_emphasis", label: "Basson korostus", profileFeature: "bass_ratio" },
  { key: "harmonic_darkness", label: "Harmoninen tummuus", profileFeature: "major_mode" },
  { key: "melancholy", label: "Melankolia" },
  { key: "euphoria", label: "Euforia" },
  { key: "hypnotic_repetition", label: "Hypnoottinen toisto", profileFeature: "rhythmic_repetition" },
  { key: "tension", label: "Musiikillinen jännite", profileFeature: "tonal_tension" },
  { key: "texture_density", label: "Tekstuurin tiheys", profileFeature: "texture_density" },
  { key: "experimentation", label: "Kokeellisuus (Tuntematon alue)" },
];

const EMPTY: Controls = {
  genre: "",
  target_bpm: null,
  rhythmic_intensity: null,
  bass_emphasis: null,
  harmonic_darkness: null,
  melancholy: null,
  euphoria: null,
  hypnotic_repetition: null,
  tension: null,
  texture_density: null,
  vocal: "instrumental",
  experimentation: null,
  duration_seconds: null,
  extra_exclude: "",
};

function OptSlider({ label, value, onChange, hint }: { label: string; value: number | null; onChange: (v: number | null) => void; hint?: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2 text-sm">
        <span className={value === null ? "text-muted" : "text-ink"}>{label}</span>
        {value === null ? (
          <button type="button" onClick={() => onChange(5)} className="text-2xs text-faint hover:text-violet-soft">
            {hint ?? "johdetaan näytöstä"} · aseta
          </button>
        ) : (
          <span className="flex items-center gap-2">
            <span className="font-mono text-violet-soft">{value}</span>
            <button type="button" onClick={() => onChange(null)} className="text-2xs text-faint hover:text-ink">
              nollaa
            </button>
          </span>
        )}
      </div>
      {value !== null && <input type="range" min={0} max={10} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full" aria-label={label} />}
    </div>
  );
}

export default function PromptStudioPage() {
  const assets = useAssets();
  const profile = useProfile();
  const options = useQuery({ queryKey: ["prompt-options"], queryFn: api.promptOptions, staleTime: Infinity });
  const history = useQuery({ queryKey: qk.prompts, queryFn: api.prompts });
  const [sources, setSources] = useState<number[]>([]);
  const [objective, setObjective] = useState<string>("release");
  const [c, setC] = useState<Controls>(EMPTY);
  const [q, setQ] = useState("");
  const [batch, setBatch] = useState<string | null>(null);
  const [view, setView] = useState<"new" | "history">("new");
  const [histFilter, setHistFilter] = useState<"all" | "saved">("all");

  const gen = useMutation({
    mutationFn: () =>
      api.generatePrompts({
        source_asset_ids: sources,
        objective,
        controls: {
          ...Object.fromEntries(Object.entries(c).filter(([k, v]) => v !== null && v !== "" && k !== "extra_exclude" && k !== "genre")),
          genre: c.genre.trim() || null,
          vocal: c.vocal,
          extra_exclude: c.extra_exclude.split(",").map((s) => s.trim()).filter(Boolean),
        },
      }),
    onSuccess: (r) => {
      setBatch(r.batch_id);
      history.refetch();
    },
  });

  const analysed = (assets.data ?? []).filter((a) => a.status === "completed");
  const filtered = analysed.filter((a) => !q || `${a.title} ${a.artist}`.toLowerCase().includes(q.toLowerCase()));
  const top = new Set(profile.data?.group_definition.top ?? []);
  const p = profile.data;
  const profileReady = p?.targets.basis === "strongest_responses";
  const tempoHint = p?.targets.features.find((f) => f.feature === "tempo_bpm");
  const batchPrompts = useMemo(() => (history.data ?? []).filter((x) => x.batch_id === batch && !x.parent_id).sort((a, b) => a.id - b.id), [history.data, batch]);
  const [active, setActive] = useState(0);
  const histList = (history.data ?? []).filter((x) => histFilter === "all" || x.saved);
  const canGenerate = sources.length > 0 || profileReady;

  return (
    <div>
      <PageHeader
        eyebrow="Prompt Studio · Suno"
        icon={<PromptIcon size={14} />}
        title="Suno Prompt Studio"
        description="Muuntaa SonicDNA-havainnot kolmeksi erilaiseksi, muokattavaksi Suno-kehotteeksi. Kopioi kentät Sunon Custom Modeen, luo musiikkia ja tuo tulos takaisin analysoitavaksi."
        actions={<Tabs value={view} onChange={setView} tabs={[{ key: "new", label: "Uusi kehote" }, { key: "history", label: `Historia (${history.data?.length ?? 0})` }]} />}
      />

      {view === "history" ? (
        <div className="flex flex-col gap-4">
          <Tabs value={histFilter} onChange={setHistFilter} tabs={[{ key: "all", label: "Kaikki" }, { key: "saved", label: "Tallennetut" }]} className="self-start" />
          {histList.length === 0 ? (
            <Panel>
              <Empty title="Ei kehotteita">Luo ensimmäiset kehotteet Uusi kehote -välilehdellä.</Empty>
            </Panel>
          ) : (
            histList.map((pr) => <PromptCard key={pr.id} prompt={pr} compareCandidates={history.data ?? []} />)
          )}
        </div>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[400px_minmax(0,1fr)]">
          <div className="flex flex-col gap-5">
            <Panel eyebrow="1 · Lähteet" title="Valitse lähdekappaleet">
              {assets.isLoading ? (
                <Spinner />
              ) : analysed.length === 0 ? (
                <p className="text-sm text-muted">Analysoi ensin kappaleita kirjastossa.</p>
              ) : (
                <>
                  <label className="relative mb-2 block">
                    <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-faint" />
                    <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Hae…" aria-label="Hae lähteitä" className="h-8 w-full rounded-lg border border-line bg-obsidian/60 pr-3 pl-8 text-sm focus:border-violet/60 focus:outline-none" />
                  </label>
                  <ul className="max-h-64 overflow-y-auto rounded-lg border border-line">
                    {filtered.map((a) => {
                      const on = sources.includes(a.id);
                      return (
                        <li key={a.id}>
                          <label className={clsx("flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-surface/40", on && "bg-violet/10")}>
                            <input type="checkbox" checked={on} onChange={() => setSources((s) => (on ? s.filter((x) => x !== a.id) : [...s, a.id].slice(0, 12)))} className="accent-violet" />
                            <span className="min-w-0 flex-1 truncate">{a.title}</span>
                            {top.has(a.id) && <span className="shrink-0 rounded bg-gold/15 px-1.5 text-[10px] text-gold" title="Kuuluu voimakkaimpiin kokemuksiisi">vahva</span>}
                            {a.origin === "generated" && <span className="shrink-0 text-[10px] text-gold">Suno</span>}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                  <p className="mt-2 text-2xs text-faint">
                    {sources.length} valittu.{" "}
                    {profileReady ? `Profiili v${p?.version} (${p?.targets.tracks.length} voimakkainta kappaletta) on käytössä myös ilman lähteitä.` : "Profiilissa ei vielä ole voimakkaimpien kokemusten ryhmää – valitse vähintään yksi lähde."}
                  </p>
                </>
              )}
            </Panel>

            <Panel eyebrow="2 · Tavoite" title="Mitä kokemusta voimistetaan?">
              <div className="flex flex-wrap gap-1.5">
                {(options.data?.objectives ?? []).map((o) => (
                  <Chip key={o.key} active={objective === o.key} onClick={() => setObjective(o.key)}>
                    {o.label}
                    {(p?.counts.ratings_by_dimension[o.dimension] ?? 0) >= 4 && <span className="ml-1 text-gold" title="Sinulla on omia arvioita tästä ulottuvuudesta">●</span>}
                  </Chip>
                ))}
              </div>
              <p className="mt-3 text-2xs text-faint">Tavoite ohjaa variaatiota B. ● = sinulla on vähintään 4 omaa arviota tästä ulottuvuudesta, joten painotus voi perustua omiin havaintoihisi.</p>
            </Panel>

            <Panel eyebrow="3 · Säädöt" title="Valinnaiset säädöt">
              <div className="flex flex-col gap-4">
                <p className="text-xs text-muted">Asettamattomat säädöt johdetaan mitatuista lähteistä ja profiilista. Sovellus ei keksi mieltymyksiäsi.</p>
                <label className="block text-sm">
                  <span className="mb-1 block">Genre tai genreyhdistelmä</span>
                  <input value={c.genre} onChange={(e) => setC({ ...c, genre: e.target.value })} placeholder="esim. downtempo, dark ambient" className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block text-sm">
                    <span className="mb-1 block">Tavoitetempo (BPM)</span>
                    <input type="number" min={40} max={220} value={c.target_bpm ?? ""} placeholder={tempoHint ? `profiili ~${Math.round(tempoHint.median)}` : "johdetaan"} onChange={(e) => setC({ ...c, target_bpm: e.target.value ? Number(e.target.value) : null })} className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block">Kesto (s)</span>
                    <input type="number" min={30} max={480} value={c.duration_seconds ?? ""} placeholder="~210" onChange={(e) => setC({ ...c, duration_seconds: e.target.value ? Number(e.target.value) : null })} className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
                  </label>
                </div>
                <label className="block text-sm">
                  <span className="mb-1 block">Laulu</span>
                  <select value={c.vocal} onChange={(e) => setC({ ...c, vocal: e.target.value })} className="h-9 w-full rounded-lg border border-line bg-obsidian px-2 text-sm">
                    {(options.data?.vocal_options ?? []).map((v) => (
                      <option key={v.key} value={v.key}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                </label>
                <details>
                  <summary className="cursor-pointer text-sm text-violet-soft select-none">Musiikilliset painotukset</summary>
                  <div className="mt-3 flex flex-col gap-3">
                    {SLIDERS.map((s) => {
                      const tf = s.profileFeature ? p?.targets.features.find((f) => f.feature === s.profileFeature) : undefined;
                      return <OptSlider key={s.key} label={s.label} value={c[s.key] as number | null} onChange={(v) => setC({ ...c, [s.key]: v })} hint={tf && tf.direction !== "typical" ? `profiili: ${tf.direction === "high" ? "korkea" : "matala"}` : undefined} />;
                    })}
                  </div>
                </details>
                <label className="block text-sm">
                  <span className="mb-1 block">Lisäpoissulut (pilkuin)</span>
                  <input value={c.extra_exclude} onChange={(e) => setC({ ...c, extra_exclude: e.target.value })} placeholder="esim. autotune, brass" className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
                </label>
              </div>
            </Panel>
            <Button variant="primary" className="h-12 text-base" disabled={!canGenerate} loading={gen.isPending} onClick={() => gen.mutate()}>
              <Wand2 className="size-4" /> Luo kolme kehotetta
            </Button>
            <ErrorNote error={gen.error} />
          </div>

          <div className="min-w-0">
            {batchPrompts.length === 0 ? (
              <Panel>
                <Empty title="Kolme luovaa suuntaa" icon={<Sparkles className="size-7" />}>
                  <span className="block">
                    <b className="text-ink">A · Syvä resonanssi</b> – toistaa voimakkaimpiin kokemuksiisi liittyvät rakenteelliset piirteet.
                  </span>
                  <span className="mt-1 block">
                    <b className="text-ink">B · Tunteen voimistaminen</b> – säilyttää ytimen mutta siirtää valittua kokemusta kohti.
                  </span>
                  <span className="mt-1 block">
                    <b className="text-ink">C · Tuntematon alue</b> – hallittu kokeilu: ankkurit pysyvät, ympäristö vaihtuu.
                  </span>
                  {p && p.summary_lines.length > 0 && (
                    <span className="mt-4 block text-left">
                      <span className="eyebrow mb-2 block">Profiilisi vahvimmat taipumukset</span>
                      {p.summary_lines.slice(0, 3).map((l) => (
                        <span key={l.feature} className="mb-1 flex items-center justify-between gap-2 text-xs">
                          {l.text} <EvidenceBadge level={l.evidence_level} />
                        </span>
                      ))}
                    </span>
                  )}
                </Empty>
              </Panel>
            ) : (
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Tabs value={String(active)} onChange={(k) => setActive(Number(k))} tabs={batchPrompts.map((pr, i) => ({ key: String(i), label: `${["A", "B", "C"][i] ?? i + 1} · ${pr.effective.mode_label}` }))} />
                  <span className="text-2xs text-faint">Luotu {fmtDate(batchPrompts[0].created_at)} · tallennettu historiaan</span>
                </div>
                {batchPrompts[active] && <PromptCard key={batchPrompts[active].id} prompt={batchPrompts[active] as PromptRecord} compareCandidates={batchPrompts} />}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
