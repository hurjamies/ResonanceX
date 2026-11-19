import clsx from "clsx";
import { AlertTriangle, Library, Pause, Play, RotateCw, Search, Sparkles, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Empty, ErrorNote, Modal, PageHeader, Panel, Spinner, Tabs } from "@/components/ui";
import { api, qk, useAssets, useInvalidateDerived } from "@/services/api";
import { fmtTime, STAGE_FI } from "@/services/format";
import { usePlayer } from "@/stores/player";
import type { Asset, UploadResult } from "@/types/api";
import { UploadResults, Uploader } from "./Uploader";

export function StatusPill({ a }: { a: Asset }) {
  if (a.status === "completed") return <span className="rounded-full bg-ok/10 px-2 py-0.5 text-2xs text-ok">Analysoitu</span>;
  if (a.status === "failed")
    return (
      <span className="rounded-full bg-danger/10 px-2 py-0.5 text-2xs text-danger" title={a.error ?? ""}>
        Epäonnistui
      </span>
    );
  if (a.status === "processing" && a.job)
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-violet/10 px-2 py-0.5 text-2xs text-violet-soft">
        <span className="relative flex size-1.5">
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-violet-soft" />
          <span className="relative size-1.5 rounded-full bg-violet-soft" />
        </span>
        {STAGE_FI[a.job.stage ?? ""] ?? "Käsitellään"} · {a.job.stages_done + 1}/{a.job.stages_total}
      </span>
    );
  return <span className="rounded-full bg-surface px-2 py-0.5 text-2xs text-muted">Jonossa</span>;
}

function PlayButton({ a }: { a: Asset }) {
  const { assetId, playing, load, toggle } = usePlayer();
  const active = assetId === a.id;
  return (
    <button
      onClick={() => (active ? toggle() : load(a, true))}
      className={clsx("grid size-9 shrink-0 place-items-center rounded-full border transition-colors", active && playing ? "border-violet bg-violet text-white" : "border-line-strong text-muted hover:border-violet hover:text-ink")}
      aria-label={active && playing ? `Tauko: ${a.title}` : `Toista: ${a.title}`}
    >
      {active && playing ? <Pause className="size-3.5" /> : <Play className="size-3.5 translate-x-px" />}
    </button>
  );
}

export default function LibraryPage() {
  const assets = useAssets();
  const qc = useQueryClient();
  const inv = useInvalidateDerived();
  const [filter, setFilter] = useState<"all" | "library" | "generated" | "unrated">("all");
  const [q, setQ] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [confirmDel, setConfirmDel] = useState<Asset | null>(null);
  const [lastResults, setLastResults] = useState<UploadResult[] | null>(null);

  const del = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.assets });
      inv();
      setConfirmDel(null);
    },
  });
  const retry = useMutation({ mutationFn: (id: number) => api.reanalyze(id), onSuccess: () => qc.invalidateQueries({ queryKey: qk.assets }) });

  const list = useMemo(() => {
    let l = assets.data ?? [];
    if (filter === "library") l = l.filter((a) => a.origin === "library");
    if (filter === "generated") l = l.filter((a) => a.origin === "generated");
    if (filter === "unrated") l = l.filter((a) => a.status === "completed" && !a.rated);
    if (q.trim()) {
      const s = q.toLowerCase();
      l = l.filter((a) => `${a.title} ${a.artist} ${a.original_filename}`.toLowerCase().includes(s));
    }
    return l;
  }, [assets.data, filter, q]);

  const total = assets.data?.length ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="Kirjasto"
        icon={<Library className="size-3.5" />}
        title="Kirjasto"
        description="Kaikki tuodut kappaleet ja Sunolla luodut tulokset. Tuo myös musiikkia, joka ei vaikuta sinuun – vertailu tarvitsee molempia."
        actions={
          <Button variant="primary" onClick={() => setUploadOpen(true)}>
            Tuo musiikkia
          </Button>
        }
      />

      {assets.isLoading ? (
        <Spinner />
      ) : total === 0 ? (
        <Panel>
          <div className="mx-auto max-w-xl py-4">
            <Empty title="Kirjasto on tyhjä" icon={<Sparkles className="size-7" />}>
              Aloita tuomalla muutama kappale. SonicDNA analysoi niiden rytmin, spektrin, harmonian, dynamiikan ja rakenteen paikallisesti.
            </Empty>
            <Uploader onDone={setLastResults} />
          </div>
        </Panel>
      ) : (
        <>
        {lastResults && (
          <Panel className="mb-4" eyebrow="Viimeisin tuonti" actions={<Button size="sm" variant="ghost" onClick={() => setLastResults(null)}>Sulje</Button>}>
            <UploadResults results={lastResults} />
          </Panel>
        )}
        <Panel bodyClass="p-0 sm:p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
            <Tabs
              value={filter}
              onChange={setFilter}
              tabs={[
                { key: "all", label: `Kaikki ${total}` },
                { key: "library", label: "Kirjasto" },
                { key: "generated", label: "Generoidut" },
                { key: "unrated", label: "Arvioimatta" },
              ]}
            />
            <label className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-faint" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Hae…" aria-label="Hae kappaleita" className="h-8 w-48 rounded-lg border border-line bg-obsidian/60 pr-3 pl-8 text-sm placeholder:text-faint focus:border-violet/60 focus:outline-none" />
            </label>
          </div>
          <ul className="divide-y divide-line">
            {list.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-4 py-3 hover:bg-surface/30">
                <PlayButton a={a} />
                <div className="min-w-0 flex-1">
                  <Link to={`/tracks/${a.id}`} className="block truncate text-sm font-medium text-ink hover:text-violet-soft">
                    {a.title || a.original_filename}
                  </Link>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                    {a.artist && <span className="truncate">{a.artist}</span>}
                    <span className="font-mono tabular">{fmtTime(a.duration_seconds)}</span>
                    {a.origin === "generated" && <span className="rounded border border-gold/30 px-1 text-[10px] text-gold">Suno-tulos</span>}
                    {a.rated && <span className="text-gold">● arvioitu</span>}
                    {a.marker_count > 0 && <span>{a.marker_count} merkintää</span>}
                  </div>
                  {a.status === "failed" && <div className="mt-1 flex items-center gap-1 text-xs text-danger"><AlertTriangle className="size-3" />{a.error}</div>}
                </div>
                <div className="hidden sm:block">
                  <StatusPill a={a} />
                </div>
                <div className="flex items-center">
                  {a.status === "failed" && (
                    <Button size="sm" variant="ghost" onClick={() => retry.mutate(a.id)} aria-label="Yritä analyysia uudelleen">
                      <RotateCw className="size-3.5" />
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => setConfirmDel(a)} aria-label={`Poista ${a.title}`}>
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </li>
            ))}
            {list.length === 0 && <li className="px-4 py-8 text-center text-sm text-muted">Ei hakua vastaavia kappaleita.</li>}
          </ul>
        </Panel>
        </>
      )}

      <Modal open={uploadOpen} onClose={() => setUploadOpen(false)} title="Tuo musiikkia">
        <Uploader onDone={setLastResults} />
      </Modal>
      <Modal open={!!confirmDel} onClose={() => setConfirmDel(null)} title="Poista kappale">
        <p className="text-sm text-muted">
          Poistetaanko <span className="text-ink">{confirmDel?.title}</span>? Myös sen analyysi, arviot, merkinnät ja vertailut poistetaan pysyvästi.
        </p>
        <ErrorNote error={del.error} />
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmDel(null)}>
            Peruuta
          </Button>
          <Button variant="danger" loading={del.isPending} onClick={() => confirmDel && del.mutate(confirmDel.id)}>
            Poista pysyvästi
          </Button>
        </div>
      </Modal>
    </div>
  );
}
