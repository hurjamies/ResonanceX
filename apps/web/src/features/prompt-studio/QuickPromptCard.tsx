import { ExternalLink, FileUp } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, CopyButton, Modal } from "@/components/ui";
import { Uploader } from "@/features/library/Uploader";
import type { PromptRecord } from "@/types/api";

/** A short hand-off to Suno; the full editor remains one click away. */
export function QuickPromptCard({ prompt }: { prompt: PromptRecord }) {
  const [importOpen, setImportOpen] = useState(false);
  const e = prompt.effective;
  return <article className="panel p-5 sm:p-7">
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="mb-1 text-sm text-violet-soft">{e.mode_label}</p>
        <h2 className="break-words text-2xl font-semibold">{e.title}</h2>
        <p className="mt-1 text-sm text-muted">{e.hybrid_genre ?? e.primary_genre ?? "Suosikkiesi pohjalta"}</p>
      </div>
      <CopyButton text={e.title} label="Kopioi nimi" />
    </div>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-base font-medium">1. Kopioi tyylikuvaus Sunon Styles-kenttään</h3>
      <CopyButton text={e.style} label="Kopioi tyyli" />
    </div>
    <p className="rounded-xl bg-obsidian p-4 text-base leading-relaxed">{e.style}</p>
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-base font-medium">2. Avaa Suno ja luo kappale</h3>
      <a href={e.suno_url} target="_blank" rel="noreferrer noopener" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-soft">Avaa Suno <ExternalLink className="size-4" /></a>
    </div>
    <p className="mt-2 text-sm text-muted">Käytä Sunon Custom-tilaa. {e.instrumental ? "Valitse Instrumental." : "Voit käyttää Sunon sanoitustoimintoa tai kirjoittaa omat sanat."}</p>
    <details className="mt-6 border-t border-line pt-4">
      <summary className="cursor-pointer text-sm text-muted hover:text-ink">Rakenne ja lisäasetukset</summary>
      <div className="mt-4 flex flex-col gap-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2"><span>Rakenne Lyrics-kenttään</span><CopyButton text={e.lyrics} label="Kopioi rakenne" /></div>
        <pre className="whitespace-pre-wrap rounded-xl bg-obsidian p-4 text-sm">{e.lyrics}</pre>
        <p className="text-muted">{e.lyrics_note_fi}</p>
        {e.exclude ? <div className="flex flex-wrap items-center justify-between gap-2"><span className="min-w-0 flex-1 break-words">Vältä: {e.exclude}</span><CopyButton text={e.exclude} label="Kopioi poissulut" /></div> : null}
        <p className="text-muted">{e.instrumental ? "Instrumentaali" : `Laulusuunta: ${e.vocal}`} · Weirdness {e.settings.weirdness} % · Style Influence {e.settings.style_influence} %</p>
      </div>
    </details>
    <details className="mt-4 border-t border-line pt-4">
      <summary className="cursor-pointer text-sm text-muted hover:text-ink">Mihin ehdotus perustuu?</summary>
      <ul className="mt-3 flex list-inside list-disc flex-col gap-2 text-sm text-muted">{e.evidence_fi.map((line, i) => <li key={i}>{line}</li>)}</ul>
      <ul className="mt-3 flex list-inside list-disc flex-col gap-2 text-sm text-muted">{e.uncertainty_fi.map((line, i) => <li key={i}>{line}</li>)}</ul>
    </details>
    <div className="mt-6 border-t border-line pt-5">
      <h3 className="mb-3 text-base font-medium">3. Kuuntele tulos ja auta löytämään vielä parempi suunta</h3>
      <Button onClick={() => setImportOpen(true)}><FileUp className="size-4" /> Tuo Sunosta lataamasi kappale</Button>
      {prompt.generated_assets?.length ? <div className="mt-3 flex flex-wrap gap-3 text-sm">{prompt.generated_assets.map((a) => <Link key={a.id} to={`/tracks/${a.id}`} className="text-violet-soft hover:underline">Kuuntele ja arvioi: {a.title}</Link>)}</div> : null}
    </div>
    <Modal open={importOpen} onClose={() => setImportOpen(false)} title="Tuo Suno-tulos"><Uploader promptId={prompt.id} folderId={prompt.specification.extra?.music_library?.folder_id} /></Modal>
  </article>;
}
