import clsx from "clsx";
import { CheckCircle2, CircleAlert, Copy, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Button, ErrorNote } from "@/components/ui";
import { useUpload, useVocabulary } from "@/services/api";
import type { UploadResult } from "@/types/api";

/** Batch audio upload with explicit rights confirmation. */
export function Uploader({ promptId, compact, onDone }: { promptId?: number; compact?: boolean; onDone?: (r: UploadResult[]) => void }) {
  const vocab = useVocabulary();
  const upload = useUpload();
  const [files, setFiles] = useState<File[]>([]);
  const [rights, setRights] = useState(false);
  const [drag, setDrag] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const accept = (vocab.data?.allowed_extensions ?? [".mp3", ".wav", ".flac", ".m4a"]).join(",");

  const add = (list: FileList | null) => {
    if (!list) return;
    setResults(null);
    setFiles((prev) => [...prev, ...Array.from(list)].slice(0, promptId ? 1 : 50));
  };

  const submit = async () => {
    const res = await upload.mutateAsync({ files, rights, promptId });
    setResults(res.results);
    setFiles([]);
    onDone?.(res.results);
  };

  return (
    <div className="flex flex-col gap-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          add(e.dataTransfer.files);
        }}
        className={clsx(
          "relative flex flex-col items-center justify-center rounded-xl border border-dashed text-center transition-colors",
          compact ? "px-4 py-6" : "px-6 py-10",
          drag ? "border-cyan bg-cyan/5" : "border-line-strong bg-obsidian/40 hover:border-violet/50",
        )}
      >
        <Upload className="mb-3 size-6 text-violet-soft" />
        <p className="text-sm text-ink">{promptId ? "Pudota Sunosta ladattu kappale tähän" : "Pudota äänitiedostoja tähän"}</p>
        <p className="mt-1 text-xs text-muted">MP3, WAV, FLAC, M4A, OGG, AIFF · {promptId ? "1 tiedosto" : "useita kerralla"}</p>
        <Button size="sm" className="mt-4" onClick={() => input.current?.click()}>
          Valitse tiedostot
        </Button>
        <input ref={input} type="file" multiple={!promptId} accept={accept} className="sr-only" onChange={(e) => add(e.target.files)} aria-label="Valitse äänitiedostot" />
      </div>

      {files.length > 0 && (
        <ul className="divide-y divide-line rounded-lg border border-line text-sm">
          {files.map((f, i) => (
            <li key={i} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="truncate">{f.name}</span>
              <span className="shrink-0 font-mono text-xs text-muted">{(f.size / 1024 / 1024).toFixed(1)} Mt</span>
            </li>
          ))}
        </ul>
      )}

      <label className="flex items-start gap-3 text-sm text-muted">
        <input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} className="mt-0.5 size-4 accent-violet" />
        <span>
          Vahvistan, että minulla on oikeus käyttää näitä tiedostoja henkilökohtaiseen analyysiin. Tiedostot tallennetaan ja analysoidaan vain paikallisesti, eikä niitä lähetetä
          ulkoisiin palveluihin. Analyysi ei anna oikeutta käyttää teoksia kaupallisesti.
        </span>
      </label>

      <div className="flex items-center gap-3">
        <Button variant="primary" disabled={!files.length || !rights} loading={upload.isPending} onClick={submit}>
          {promptId ? "Tuo ja analysoi tulos" : `Tuo ${files.length || ""} ja analysoi`}
        </Button>
        {files.length > 0 && (
          <Button variant="ghost" onClick={() => setFiles([])}>
            Tyhjennä
          </Button>
        )}
      </div>
      <ErrorNote error={upload.error} />

      {results && <UploadResults results={results} />}
    </div>
  );
}

export function UploadResults({ results }: { results: UploadResult[] }) {
  return (
    <ul className="flex flex-col gap-1.5 text-sm" aria-live="polite">
      {results.map((r, i) => (
        <li key={i} className="flex items-start gap-2">
          {r.ok ? (
            r.duplicate ? <Copy className="mt-0.5 size-4 shrink-0 text-gold" /> : <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" />
          ) : (
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
          )}
          <span className="min-w-0">
            <span className="text-ink">{r.filename}</span>{" "}
            <span className="text-muted">{r.ok ? (r.duplicate ? "– on jo kirjastossa (sama tiedosto), käytetään olemassa olevaa." : "– lisätty analyysijonoon.") : `– ${r.error}`}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
