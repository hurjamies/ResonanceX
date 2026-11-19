import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, GitCompare, Pause, Play, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, CategoryBadge, ErrorNote, PageHeader, Panel, Spinner } from "@/components/ui";
import { api, qk, useAssets, useInvalidateDerived } from "@/services/api";
import { fmtDate } from "@/services/format";
import { usePlayer } from "@/stores/player";
import type { Asset } from "@/types/api";

type Choice = "a" | "b" | "equal" | null;

function Side({ label, asset, options, onPick }: { label: "A" | "B"; asset: Asset | undefined; options: Asset[]; onPick: (id: number) => void }) {
  const { assetId, playing, load, toggle } = usePlayer();
  const active = asset && assetId === asset.id;
  return (
    <div className={clsx("rounded-xl border p-4", label === "A" ? "border-violet/40" : "border-cyan/40")}>
      <div className="mb-3 flex items-center justify-between">
        <span className={clsx("font-display text-2xl font-semibold", label === "A" ? "text-violet-soft" : "text-cyan")}>{label}</span>
        {asset && (
          <button onClick={() => (active ? toggle() : load(asset, true))} className="grid size-10 place-items-center rounded-full border border-line-strong hover:border-violet" aria-label={`Toista ${label}`}>
            {active && playing ? <Pause className="size-4" /> : <Play className="size-4 translate-x-px" />}
          </button>
        )}
      </div>
      <select value={asset?.id ?? ""} onChange={(e) => onPick(Number(e.target.value))} aria-label={`Kappale ${label}`} className="h-10 w-full rounded-lg border border-line bg-obsidian px-2 text-sm">
        <option value="">Valitse kappale…</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.title}
            {o.artist ? ` – ${o.artist}` : ""}
          </option>
        ))}
      </select>
      {asset && (
        <Link to={`/tracks/${asset.id}`} className="mt-2 block text-xs text-muted hover:text-ink">
          Avaa analyysi →
        </Link>
      )}
    </div>
  );
}

function Question({ q, value, onChange }: { q: string; value: Choice; onChange: (c: Choice) => void }) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm text-ink">{q}</legend>
      <div className="grid grid-cols-3 gap-2">
        {(["a", "equal", "b"] as const).map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={value === c}
            onClick={() => onChange(value === c ? null : c)}
            className={clsx(
              "rounded-lg border py-2.5 text-sm transition-colors",
              value === c ? (c === "a" ? "border-violet bg-violet/15 text-ink" : c === "b" ? "border-cyan bg-cyan/15 text-ink" : "border-gold bg-gold/10 text-ink") : "border-line text-muted hover:text-ink",
            )}
          >
            {c === "a" ? "A" : c === "b" ? "B" : "Yhtä paljon"}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export default function ComparePage() {
  const [params] = useSearchParams();
  const assets = useAssets();
  const qc = useQueryClient();
  const inv = useInvalidateDerived();
  const comps = useQuery({ queryKey: qk.comparisons, queryFn: api.comparisons });
  const [a, setA] = useState<number | null>(params.get("a") ? Number(params.get("a")) : null);
  const [b, setB] = useState<number | null>(params.get("b") ? Number(params.get("b")) : null);
  const [stronger, setStronger] = useState<Choice>(null);
  const [enjoyed, setEnjoyed] = useState<Choice>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const analysed = (assets.data ?? []).filter((x) => x.status === "completed");
  const byId = Object.fromEntries(analysed.map((x) => [x.id, x]));

  const save = useMutation({
    mutationFn: () => api.createComparison({ asset_a_id: a!, asset_b_id: b!, stronger, enjoyed, note: note.trim() || null, suggested_by_core: params.get("suggested") === "1" }),
    onSuccess: () => {
      setSaved(true);
      setStronger(null);
      setEnjoyed(null);
      setNote("");
      qc.invalidateQueries({ queryKey: qk.comparisons });
      inv();
    },
  });
  const del = useMutation({ mutationFn: (id: number) => api.deleteComparison(id), onSuccess: () => { qc.invalidateQueries({ queryKey: qk.comparisons }); inv(); } });

  if (assets.isLoading) return <Spinner />;
  return (
    <div>
      <Link to="/sonic-dna" className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" /> SonicDNA
      </Link>
      <PageHeader
        eyebrow="Pareittaisvertailu"
        icon={<GitCompare className="size-3.5" />}
        title="Kumpi vaikuttaa sinuun enemmän?"
        description="Suora vertailu on usein luotettavampi kuin erilliset numeroarviot. Voimakkuus ja mieluisuus kysytään erikseen, koska ne eivät ole sama asia."
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Panel eyebrow={<span className="flex items-center gap-2">Uusi vertailu <CategoryBadge cat="self_reported" /></span>}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Side label="A" asset={a ? byId[a] : undefined} options={analysed.filter((x) => x.id !== b)} onPick={(id) => { setA(id || null); setSaved(false); }} />
            <Side label="B" asset={b ? byId[b] : undefined} options={analysed.filter((x) => x.id !== a)} onPick={(id) => { setB(id || null); setSaved(false); }} />
          </div>
          <div className="mt-6 flex flex-col gap-5">
            <Question q="Kumpi vaikuttaa sinuun voimakkaammin?" value={stronger} onChange={setStronger} />
            <Question q="Kumpi on sinulle mieluisampi?" value={enjoyed} onChange={setEnjoyed} />
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Miksi? (valinnainen)" aria-label="Perustelu" className="h-10 rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
            <div className="flex items-center gap-3">
              <Button variant="primary" disabled={!a || !b || (!stronger && !enjoyed)} loading={save.isPending} onClick={() => save.mutate()}>
                Tallenna vertailu
              </Button>
              {saved && <span className="text-sm text-ok">Tallennettu – profiili päivittyy.</span>}
            </div>
            <ErrorNote error={save.error} />
          </div>
        </Panel>
        <Panel eyebrow="Historia" title={`Vertailut (${comps.data?.length ?? 0})`}>
          {!comps.data?.length ? (
            <p className="text-sm text-muted">Ei vielä vertailuja.</p>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {comps.data.map((c) => {
                const A = byId[c.asset_a_id]?.title ?? `#${c.asset_a_id}`;
                const B = byId[c.asset_b_id]?.title ?? `#${c.asset_b_id}`;
                const w = (x: Choice) => (x === "a" ? A : x === "b" ? B : x === "equal" ? "yhtä paljon" : "–");
                return (
                  <li key={c.id} className="rounded-lg border border-line p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 text-xs text-muted">
                        <span className="text-violet-soft">A</span> {A} <span className="text-faint">vs</span> <span className="text-cyan">B</span> {B}
                      </div>
                      <button onClick={() => del.mutate(c.id)} className="text-faint hover:text-danger" aria-label="Poista vertailu">
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                    <div className="mt-1.5 text-xs">
                      Voimakkaampi: <span className="text-ink">{w(c.stronger)}</span> · Mieluisampi: <span className="text-ink">{w(c.enjoyed)}</span>
                    </div>
                    <div className="mt-1 text-2xs text-faint">{fmtDate(c.created_at)}</div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
