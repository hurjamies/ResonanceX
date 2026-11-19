import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Maximize2, Pause, Play, RotateCw, SkipBack, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button, CategoryBadge, Empty, ErrorNote, Panel, Spinner } from "@/components/ui";
import { SonicIcon } from "@/design-system/brand";
import { api, qk, useAsset } from "@/services/api";
import { fmtBytes, fmtTime, STAGE_FI } from "@/services/format";
import { usePlayer } from "@/stores/player";
import { StatusPill } from "@/features/library/LibraryPage";
import { AnalysisPanels, MomentInspector } from "./AnalysisPanels";
import { MarkersPanel } from "./MarkersPanel";
import { RatingPanel } from "./RatingPanel";
import { SimilarPanel } from "./SimilarPanel";
import { Timeline } from "./timeline";

function Transport({ duration }: { duration: number }) {
  const { playing, toggle, seek, zoom, fit, view, selection, setView, currentTime } = usePlayer();
  const zoomed = view.start > 0.01 || view.end < duration - 0.01;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button onClick={toggle} className="grid size-10 place-items-center rounded-full bg-violet text-white shadow-[0_0_24px_-6px_rgb(139_92_246)] hover:bg-violet-soft" aria-label={playing ? "Tauko" : "Toista"}>
        {playing ? <Pause className="size-4" /> : <Play className="size-4 translate-x-px" />}
      </button>
      <Button size="sm" variant="ghost" onClick={() => seek(Math.max(0, currentTime - 5))} aria-label="Taaksepäin 5 sekuntia">
        <SkipBack className="size-3.5" /> 5 s
      </Button>
      <div className="font-mono text-sm text-ink tabular">
        {fmtTime(currentTime, true)} <span className="text-faint">/ {fmtTime(duration)}</span>
      </div>
      <input type="range" min={0} max={duration} step={0.1} value={currentTime} onChange={(e) => seek(Number(e.target.value))} className="min-w-24 flex-1" aria-label="Toistokohta" />
      <div className="flex items-center gap-1">
        <Button size="sm" variant="ghost" onClick={() => zoom(0.5)} aria-label="Lähennä">
          <ZoomIn className="size-3.5" />
        </Button>
        <Button size="sm" variant="ghost" onClick={() => zoom(2)} aria-label="Loitonna" disabled={!zoomed}>
          <ZoomOut className="size-3.5" />
        </Button>
        {selection && (
          <Button size="sm" variant="ghost" onClick={() => setView(selection)}>
            Zoomaa valintaan
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={fit} disabled={!zoomed} aria-label="Näytä koko kappale">
          <Maximize2 className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

export default function TrackPage() {
  const id = Number(useParams().id);
  const [search] = useSearchParams();
  const startAt = search.get("t") ? Number(search.get("t")) : null;
  const asset = useAsset(id);
  const qc = useQueryClient();
  const done = asset.data?.status === "completed";
  const analysis = useQuery({ queryKey: qk.analysis(id), queryFn: () => api.analysis(id), enabled: done });
  const ts = useQuery({ queryKey: qk.ts(id), queryFn: () => api.timeseries(id), enabled: done, staleTime: Infinity });
  const markers = useQuery({ queryKey: qk.markers(id), queryFn: () => api.markers(id) });
  const load = usePlayer((s) => s.load);
  const reanalyze = useMutation({ mutationFn: () => api.reanalyze(id), onSuccess: () => qc.invalidateQueries({ queryKey: qk.asset(id) }) });

  useEffect(() => {
    if (asset.data) load(asset.data, false);
  }, [asset.data?.id, load]); // eslint-disable-line react-hooks/exhaustive-deps
  // deep link to a moment (?t=seconds), e.g. from an insight's timestamps
  useEffect(() => {
    if (startAt !== null && asset.data && Number.isFinite(startAt)) {
      const st = usePlayer.getState();
      const span = Math.min(30, asset.data.duration_seconds ?? 30);
      st.seek(startAt);
      st.setView({ start: startAt - span / 3, end: startAt - span / 3 + span });
    }
  }, [startAt, asset.data?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (done) {
      qc.invalidateQueries({ queryKey: qk.analysis(id) });
      qc.invalidateQueries({ queryKey: qk.ts(id) });
    }
  }, [done, id, qc]);

  if (asset.isLoading) return <Spinner />;
  if (asset.error || !asset.data) return <ErrorNote error={asset.error ?? "Kappaletta ei löytynyt"} />;
  const a = asset.data;
  const dur = ts.data?.duration ?? a.duration_seconds ?? 0;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link to="/library" className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
          <ArrowLeft className="size-3.5" /> Kirjasto
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <div className="eyebrow mb-2 flex items-center gap-2">
              <SonicIcon size={14} /> SonicDNA · {a.origin === "generated" ? "Suno-tulos" : "kirjasto"}
            </div>
            <h1 className="truncate text-2xl font-semibold sm:text-3xl">{a.title || a.original_filename}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
              {a.artist && <span>{a.artist}</span>}
              {a.album && <span>{a.album}</span>}
              {a.genre_tag && <span title="Tiedoston metatieto, ei analyysi">genre-tagi: {a.genre_tag}</span>}
              <span className="font-mono text-xs">
                {a.codec} · {a.sample_rate ? `${(a.sample_rate / 1000).toFixed(1)} kHz` : ""} · {a.channels === 1 ? "mono" : "stereo"} · {fmtBytes(a.size_bytes)}
              </span>
              <StatusPill a={a} />
            </div>
            {a.prompt && (
              <div className="mt-2 text-sm">
                Luotu kehotteella{" "}
                <Link to={`/experiments`} className="text-gold hover:underline">
                  #{a.prompt.id} {a.prompt.title}
                </Link>
              </div>
            )}
          </div>
          {done && analysis.data?.outdated && (
            <Button size="sm" onClick={() => reanalyze.mutate()} loading={reanalyze.isPending}>
              <RotateCw className="size-3.5" /> Päivitä analyysi uuteen versioon
            </Button>
          )}
        </div>
      </div>

      {a.status !== "completed" && (
        <Panel>
          {a.status === "failed" ? (
            <Empty title="Analyysi epäonnistui" action={<Button onClick={() => reanalyze.mutate()} loading={reanalyze.isPending}><RotateCw className="size-3.5" /> Yritä uudelleen</Button>}>
              {a.error}
            </Empty>
          ) : (
            <div className="py-6">
              <div className="mb-4 text-center text-sm text-muted">Analysoidaan paikallisesti… Voit kuunnella kappaletta sillä välin.</div>
              <ol className="mx-auto flex max-w-2xl flex-wrap justify-center gap-2">
                {Object.entries(STAGE_FI).map(([k, label], i) => {
                  const doneN = a.job?.stages_done ?? 0;
                  const state = a.status === "processing" && a.job?.stage === k ? "active" : i < doneN ? "done" : "todo";
                  return (
                    <li key={k} className={`rounded-full border px-3 py-1 text-xs ${state === "active" ? "border-violet bg-violet/15 text-ink glow-violet" : state === "done" ? "border-ok/40 text-ok" : "border-line text-faint"}`}>
                      {label}
                    </li>
                  );
                })}
              </ol>
              <div className="mt-6 flex justify-center">
                <Transport duration={a.duration_seconds ?? 0} />
              </div>
            </div>
          )}
        </Panel>
      )}

      {done && (analysis.isLoading || ts.isLoading) && <Spinner label="Ladataan analyysia…" />}
      {analysis.data && ts.data && (
        <>
          <Panel bodyClass="p-3 sm:p-4" className="overflow-hidden">
            <div className="mb-3">
              <Transport duration={dur} />
            </div>
            <Timeline analysis={analysis.data} ts={ts.data} markers={markers.data ?? []} spectrogramUrl={`/api/assets/${id}/spectrogram.png?v=${analysis.data.id}`} />
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-faint">
              <span>Klikkaa: siirry · vedä: valitse väli · Ctrl/⌘ + rulla: zoomaa · Shift + rulla: vieritä · välilyönti: toista/tauko</span>
              <span className="ml-auto flex items-center gap-1.5">
                <CategoryBadge cat="measured" /> <CategoryBadge cat="estimated" /> <CategoryBadge cat="self_reported" />
              </span>
            </div>
          </Panel>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="flex min-w-0 flex-col gap-5">
              <MomentInspector analysis={analysis.data} ts={ts.data} />
              <MarkersPanel assetId={id} markers={markers.data ?? []} />
              <AnalysisPanels analysis={analysis.data} />
              <SimilarPanel assetId={id} />
            </div>
            <div className="xl:sticky xl:top-6 xl:self-start">
              <RatingPanel assetId={id} />
            </div>
          </div>
        </>
      )}
      {!done && a.status !== "failed" && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div />
          <RatingPanel assetId={id} />
        </div>
      )}
    </div>
  );
}
