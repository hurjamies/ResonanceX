import clsx from "clsx";
import { AlertTriangle, ArrowRight, Folder, Library, Pause, Pencil, Play, Plus, RotateCw, Search, Sparkles, Trash2, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Empty, ErrorNote, Modal, PageHeader, Panel, Spinner, Tabs } from "@/components/ui";
import { api, qk, useAssets, useInvalidateDerived, useMusicFolders } from "@/services/api";
import { fmtTime, STAGE_FI } from "@/services/format";
import { usePlayer } from "@/stores/player";
import type { Asset, MusicFolder, UploadResult } from "@/types/api";
import { UploadResults, Uploader } from "./Uploader";
import { ForYouCard } from "./ForYouCard";

const SOURCE_FI: Record<string, string> = {
  elevenlabs: "ElevenLabs-tulos",
  suno_mcp: "Suno MCP -tulos",
  suno_manual: "Suno-tulos",
  manual_upload: "Generoitu tulos",
  other: "Generoitu tulos",
};

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
  const folders = useMusicFolders();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const folderParam = params.get("folder");
  const selectedFolderId = folderParam && /^\d+$/.test(folderParam) ? Number(folderParam) : null;
  const selectedFolder = folders.data?.find((f) => f.id === selectedFolderId);
  // null = closed; no folder = create; folder = rename
  const [folderForm, setFolderForm] = useState<{ folder?: MusicFolder } | null>(null);
  const [folderName, setFolderName] = useState("");
  const [confirmFolderDel, setConfirmFolderDel] = useState<MusicFolder | null>(null);
  const [filter, setFilter] = useState<"all" | "library" | "generated" | "unrated">("all");
  const [q, setQ] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [confirmDel, setConfirmDel] = useState<Asset | null>(null);
  const [lastResults, setLastResults] = useState<UploadResult[] | null>(null);

  const saveFolder = useMutation({
    mutationFn: ({ id, name }: { id?: number; name: string }) => (id ? api.renameMusicFolder(id, name) : api.createMusicFolder(name)),
    onSuccess: (f) => {
      inv();
      setFolderForm(null);
      setFolderName("");
      setParams({ folder: String(f.id) });
    },
  });
  const openFolderForm = (folder?: MusicFolder) => {
    saveFolder.reset();
    setFolderName(folder?.name ?? "");
    setFolderForm({ folder });
  };
  const deleteFolder = useMutation({
    mutationFn: (id: number) => api.deleteMusicFolder(id),
    onSuccess: (r) => {
      inv();
      if (selectedFolderId === r.deleted) setParams({});
      setConfirmFolderDel(null);
    },
  });
  const assignFolder = useMutation({
    mutationFn: ({ id, folderId }: { id: number; folderId: number | null }) => api.patchAsset(id, { folder_id: folderId }),
    onSuccess: (a) => {
      inv();
      qc.invalidateQueries({ queryKey: qk.asset(a.id) });
    },
  });
  const generate = useMutation({
    mutationFn: api.folderPrompt,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: qk.prompts });
      qc.invalidateQueries({ queryKey: qk.overview });
      navigate(`/prompt-studio?batch=${r.batch_id}&quick=1`);
    },
  });

  const del = useMutation({
    mutationFn: (id: number) => api.deleteAsset(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.assets });
      inv();
      setConfirmDel(null);
    },
  });
  const retry = useMutation({ mutationFn: (id: number) => api.reanalyze(id), onSuccess: inv });

  const list = useMemo(() => {
    let l = assets.data ?? [];
    if (folderParam === "none") l = l.filter((a) => a.folder_id === null);
    else if (selectedFolderId !== null) l = l.filter((a) => a.folder_id === selectedFolderId);
    if (filter === "library") l = l.filter((a) => a.origin === "library");
    if (filter === "generated") l = l.filter((a) => a.origin === "generated");
    if (filter === "unrated") l = l.filter((a) => a.status === "completed" && !a.rated);
    if (q.trim()) {
      const s = q.toLowerCase();
      l = l.filter((a) => `${a.title} ${a.artist} ${a.original_filename}`.toLowerCase().includes(s));
    }
    return l;
  }, [assets.data, filter, q, folderParam, selectedFolderId]);

  const total = assets.data?.length ?? 0;
  const folderTotal = (assets.data ?? []).filter((a) => folderParam === "none" ? a.folder_id === null : selectedFolderId === null || a.folder_id === selectedFolderId).length;

  return (
    <div>
      <PageHeader
        eyebrow="Kirjasto"
        icon={<Library className="size-3.5" />}
        title="Sinun musiikkisi"
        description="Omat tyylit, omat suosikit. Lisää musiikkia lokeroon ja tee siitä oman makusi mukainen Suno-kehote."
        actions={
          <Button variant="primary" onClick={() => setUploadOpen(true)}>
            <Upload className="size-4" /> Tuo musiikkia
          </Button>
        }
      />

      <div className="mb-7"><ForYouCard /></div>
      <section className="mb-7" aria-label="Tyylilokerot">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Tyylilokerosi</h2>
          <Button size="sm" onClick={() => openFolderForm()}><Plus className="size-4" /> Uusi lokero</Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {folders.data?.map((f) => <article key={f.id} className={clsx("flex min-w-0 flex-col rounded-xl border bg-midnight p-5", selectedFolderId === f.id ? "border-violet" : "border-line-strong")}>
            <div className="flex min-w-0 items-start gap-2">
              <button type="button" aria-pressed={selectedFolderId === f.id} onClick={() => { setParams({ folder: String(f.id) }); setFilter("all"); setQ(""); }} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface text-violet-soft"><Folder className="size-5" /></span>
                <span className="min-w-0"><span className="block break-words text-lg font-medium">{f.name}</span><span className="text-sm text-muted">{f.track_count} kappaletta</span></span>
              </button>
              <div className="flex shrink-0 gap-1">
                <button type="button" onClick={() => openFolderForm(f)} title="Nimeä uudelleen" aria-label={`Nimeä lokero ${f.name} uudelleen`} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface hover:text-ink"><Pencil className="size-4" /></button>
                <button type="button" onClick={() => { deleteFolder.reset(); setConfirmFolderDel(f); }} title="Poista lokero" aria-label={`Poista lokero ${f.name}`} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-danger/10 hover:text-danger"><Trash2 className="size-4" /></button>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button size="sm" variant="primary" disabled={!f.ready_count || generate.isPending} loading={generate.isPending && generate.variables === f.id} onClick={() => generate.mutate(f.id)}>Luo Suno-kehote <ArrowRight className="size-3.5" /></Button>
              <Button size="sm" variant="ghost" onClick={() => { setParams({ folder: String(f.id) }); setUploadOpen(true); }}><Plus className="size-3.5" /> Lisää musiikkia</Button>
            </div>
            {!f.ready_count ? <p className="mt-3 text-xs text-muted">{f.track_count ? "Kehotteen voi luoda, kun analyysi on valmis." : "Lisää tähän tyyliin kuuluvaa musiikkia."}</p> : null}
          </article>)}
        </div>
        {folders.isLoading ? <Spinner label="Ladataan lokeroita…" /> : null}
        <ErrorNote error={folders.error} />
        <ErrorNote error={generate.error} />
      </section>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{selectedFolder?.name ?? (folderParam === "none" ? "Ilman lokeroa" : "Kaikki kappaleet")}</h2>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={folderParam === null ? "secondary" : "ghost"} onClick={() => setParams({})}>Kaikki kappaleet</Button>
          <Button size="sm" variant={folderParam === "none" ? "secondary" : "ghost"} onClick={() => { setParams({ folder: "none" }); setFilter("all"); }}>Ilman lokeroa</Button>
        </div>
      </div>
      <ErrorNote error={assignFolder.error} />
      <ErrorNote error={assets.error} />
      {assets.isLoading ? (
        <Spinner />
      ) : total === 0 && !assets.error ? (
        <Panel>
          <div className="mx-auto max-w-xl py-4">
            <Empty title="Kirjasto on tyhjä" icon={<Sparkles className="size-7" />}>
              Valitse tyylilokero ja lisää ensimmäinen kappale. Voit kuunnella sitä jo analyysin aikana.
            </Empty>
            <Uploader key={selectedFolderId ?? "all"} folderId={selectedFolderId ?? undefined} onDone={setLastResults} />
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
                { key: "all", label: `Kaikki ${folderTotal}` },
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
              <li key={a.id} className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-surface/30 sm:flex-nowrap">
                <PlayButton a={a} />
                <div className="min-w-24 flex-1">
                  <Link to={`/tracks/${a.id}`} className="block truncate text-sm font-medium text-ink hover:text-violet-soft">
                    {a.title || a.original_filename}
                  </Link>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                    {a.artist && <span className="truncate">{a.artist}</span>}
                    <span className="font-mono tabular">{fmtTime(a.duration_seconds)}</span>
                    {a.origin === "generated" && <span className="rounded border border-gold/30 px-1 text-[10px] text-gold">{SOURCE_FI[a.source_provider ?? ""] ?? "Generoitu"}</span>}
                    {a.rated && <span className="text-gold">● arvioitu</span>}
                    {a.marker_count > 0 && <span>{a.marker_count} merkintää</span>}
                  </div>
                  {a.status === "failed" && <div className="mt-1 flex items-center gap-1 text-xs text-danger"><AlertTriangle className="size-3" />{a.error}</div>}
                </div>
                <label className="min-w-0 max-w-36 shrink-0 text-xs text-muted">
                  <span className="sr-only">Tyylilokero: {a.title || a.original_filename}</span>
                  <select aria-label={`Tyylilokero: ${a.title || a.original_filename}`} value={a.folder_id ?? ""} disabled={assignFolder.isPending} onChange={(e) => assignFolder.mutate({ id: a.id, folderId: e.target.value ? Number(e.target.value) : null })} className="min-h-10 w-full max-w-36 rounded-lg border border-line bg-midnight px-2 text-sm text-ink">
                    <option value="">Ilman lokeroa</option>
                    {folders.data?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </label>
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
            {list.length === 0 && <li className="flex flex-col items-center gap-3 px-4 py-8 text-center text-sm text-muted">{selectedFolder ? "Tässä lokerossa ei ole valintoja vastaavia kappaleita." : "Ei hakua vastaavia kappaleita."}<Button size="sm" onClick={() => setUploadOpen(true)}>Lisää musiikkia</Button></li>}
          </ul>
        </Panel>
        </>
      )}

      <Modal open={uploadOpen} onClose={() => setUploadOpen(false)} title="Tuo musiikkia">
        <Uploader key={selectedFolderId ?? "all"} folderId={selectedFolderId ?? undefined} onDone={setLastResults} />
      </Modal>
      <Modal open={!!folderForm} onClose={() => setFolderForm(null)} title={folderForm?.folder ? "Nimeä lokero uudelleen" : "Uusi tyylilokero"}>
        <form onSubmit={(e) => { e.preventDefault(); if (folderName.trim()) saveFolder.mutate({ id: folderForm?.folder?.id, name: folderName.trim() }); }} className="flex flex-col gap-4">
          <label className="flex flex-col gap-2 text-sm">Tyylilajin nimi<input autoFocus maxLength={60} required value={folderName} onChange={(e) => setFolderName(e.target.value)} placeholder="Esim. jazz, folk tai progressiivinen metalli" className="h-11 w-full rounded-lg border border-line-strong bg-obsidian px-3" /></label>
          <p className="text-sm text-muted">
            {folderForm?.folder
              ? "Uusi nimi ohjaa lokerosta tästä eteenpäin luotavia Suno-kehotteita. Jo tallennetut kehotteet eivät muutu."
              : "Nimeä lokero tyylilajin mukaan. Sama tyyli ohjaa siitä luotavia Suno-kehotteita."}
          </p>
          <Button type="submit" variant="primary" loading={saveFolder.isPending} disabled={!folderName.trim()}>{folderForm?.folder ? "Tallenna nimi" : "Luo lokero"}</Button>
          <ErrorNote error={saveFolder.error} />
        </form>
      </Modal>
      <Modal open={!!confirmFolderDel} onClose={() => setConfirmFolderDel(null)} title="Poista lokero">
        <p className="text-sm text-muted">
          Poistetaanko lokero <span className="text-ink">{confirmFolderDel?.name}</span>?{" "}
          {confirmFolderDel?.track_count
            ? `Sen ${confirmFolderDel.track_count} kappaletta säilyvät kirjastossa ja siirtyvät kohtaan Ilman lokeroa.`
            : "Lokero on tyhjä."}{" "}
          Kappaleita, arvioita tai tallennettuja kehotteita ei poisteta.
        </p>
        <ErrorNote error={deleteFolder.error} />
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmFolderDel(null)}>Peruuta</Button>
          <Button variant="danger" loading={deleteFolder.isPending} onClick={() => confirmFolderDel && deleteFolder.mutate(confirmFolderDel.id)}>Poista lokero</Button>
        </div>
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
