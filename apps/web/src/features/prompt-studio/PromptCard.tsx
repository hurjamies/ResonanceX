import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Bookmark, BookmarkCheck, Copy as CopyIcon, Download, ExternalLink, FileUp, GitCompareArrows, Pencil, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, CategoryBadge, CopyButton, ErrorNote, EvidenceBadge, Modal } from "@/components/ui";
import { api, qk, useVocabulary } from "@/services/api";
import { fmtDate, fmtFeature } from "@/services/format";
import type { EvidenceLevel, PromptRecord, SunoPackage } from "@/types/api";
import { Uploader } from "@/features/library/Uploader";
import { ProviderActions } from "./ProviderActions";

const SUPPORT_FI = {
  suno_field: { label: "Suno-kenttä", cls: "text-ok border-ok/30" },
  free_text_hint: { label: "Vapaa teksti", cls: "text-cyan border-cyan/30" },
  imperfect: { label: "Suno voi tulkita epätarkasti", cls: "text-gold border-gold/30" },
} as const;

const MODE_STYLE: Record<string, string> = {
  deep_resonance: "from-violet/25",
  intensification: "from-lavender/20",
  unknown_territory: "from-cyan/20",
};

const SOURCE_FI: Record<string, string> = {
  profile: "profiili",
  sources: "lähteet",
  user: "oma säätö",
  objective_convention: "konventio",
  personal_association: "oma yhteys",
  exploration: "kokeilu",
};

type Editable = "title" | "style" | "lyrics" | "exclude" | "creative_direction" | "primary_genre" | "hybrid_genre";

function FieldBlock({ name, label, value, support, multiline, editing, onEdit, original, note }: { name: Editable; label: string; value: string; support?: SunoPackage["field_support"][string]; multiline?: boolean; editing: boolean; onEdit: (k: Editable, v: string) => void; original: string; note?: string }) {
  const changed = value !== original;
  return (
    <div className="rounded-lg border border-line bg-obsidian/50">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/70 px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-ink">{label}</span>
          {support && (
            <span title={support.note_fi} className={clsx("rounded border px-1.5 py-px font-mono text-[9.5px] tracking-wider uppercase", SUPPORT_FI[support.kind].cls)}>
              {SUPPORT_FI[support.kind].label}
            </span>
          )}
          {changed && <span className="rounded bg-gold/15 px-1.5 text-[10px] text-gold">muokattu</span>}
        </div>
        <CopyButton text={value} label="Kopioi" />
      </div>
      {editing ? (
        multiline ? (
          <textarea value={value} onChange={(e) => onEdit(name, e.target.value)} rows={name === "lyrics" ? 8 : 4} aria-label={label} className="block w-full resize-y bg-transparent px-3 py-2 font-mono text-[12.5px] text-ink focus:outline-none" />
        ) : (
          <input value={value} onChange={(e) => onEdit(name, e.target.value)} aria-label={label} className="block w-full bg-transparent px-3 py-2 font-mono text-[12.5px] text-ink focus:outline-none" />
        )
      ) : (
        <pre className="px-3 py-2 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-ink">{value || <span className="text-faint">–</span>}</pre>
      )}
      {note && <div className="border-t border-line/50 px-3 py-1.5 text-2xs text-faint">{note}</div>}
    </div>
  );
}

export function promptAsText(e: SunoPackage): string {
  return [
    `Title: ${e.title}`,
    `Style of Music: ${e.style}`,
    `Instrumental: ${e.instrumental ? "yes" : "no"}`,
    `Exclude: ${e.exclude || "-"}`,
    "",
    "Lyrics / Structure:",
    e.lyrics,
  ].join("\n");
}

export function PromptCard({ prompt, onChanged, compareCandidates = [] }: { prompt: PromptRecord; onChanged?: (p: PromptRecord) => void; compareCandidates?: PromptRecord[] }) {
  const qc = useQueryClient();
  const vocab = useVocabulary();
  const defs = Object.fromEntries((vocab.data?.features ?? []).map((f) => [f.key, f]));
  const e = prompt.effective;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Partial<SunoPackage>>({});
  const [compareOpen, setCompareOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [compareWith, setCompareWith] = useState<number | "original">("original");
  const cur = { ...e, ...draft } as SunoPackage;
  const done = (p: PromptRecord) => {
    qc.invalidateQueries({ queryKey: qk.prompts });
    qc.invalidateQueries({ queryKey: qk.overview });
    onChanged?.(p);
  };
  const patch = useMutation({ mutationFn: (body: Parameters<typeof api.patchPrompt>[1]) => api.patchPrompt(prompt.id, body), onSuccess: done });
  const dup = useMutation({ mutationFn: () => api.duplicatePrompt(prompt.id), onSuccess: done });

  const onEdit = (k: Editable, v: string) => setDraft((d) => ({ ...d, [k]: v }));
  const saveEdits = () =>
    patch.mutate(
      { edited: { ...draft } },
      {
        onSuccess: () => {
          setEditing(false);
          setDraft({});
        },
      },
    );
  const support = e.field_support;
  const other = compareWith === "original" ? null : compareCandidates.find((c) => c.id === compareWith) ?? null;
  const left = other ? other.effective : prompt.compiled;

  return (
    <article className={clsx("panel overflow-hidden bg-gradient-to-b to-transparent", MODE_STYLE[prompt.mode])}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <div className="eyebrow mb-1">
            {e.mode_label}
            {e.objective_label ? ` · ${e.objective_label}` : ""} · #{prompt.id}
          </div>
          <h3 className="truncate font-display text-lg font-semibold">{cur.title}</h3>
          <div className="mt-0.5 text-2xs text-faint">
            {fmtDate(prompt.created_at)} · profiili v{prompt.profile_version ?? "–"} · {prompt.parent_id ? `kopio #${prompt.parent_id}` : `erä ${prompt.batch_id.slice(0, 6)}`}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <CopyButton text={promptAsText(cur)} label="Kopioi kaikki" size="sm" />
          <a href={e.suno_url} target="_blank" rel="noreferrer noopener">
            <Button size="sm" variant="primary">
              Avaa Suno <ExternalLink className="size-3.5" />
            </Button>
          </a>
        </div>
      </header>

      <div className="flex flex-col gap-3 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldBlock name="title" label="Title" value={cur.title} support={support.title} editing={editing} onEdit={onEdit} original={prompt.compiled.title} />
          <FieldBlock name="hybrid_genre" label="Hybrid genre" value={cur.hybrid_genre ?? cur.primary_genre ?? ""} support={support.hybrid_genre} editing={editing} onEdit={onEdit} original={prompt.compiled.hybrid_genre ?? prompt.compiled.primary_genre ?? ""} />
        </div>
        <FieldBlock name="style" label="Style of Music" value={cur.style} support={support.style} multiline editing={editing} onEdit={onEdit} original={prompt.compiled.style} note={`${cur.style.length} merkkiä${e.style_dropped.length ? ` · jätetty pois tiiviyden vuoksi: ${e.style_dropped.join(", ")}` : ""}`} />
        <FieldBlock name="lyrics" label="Lyrics / Structure" value={cur.lyrics} support={support.lyrics} multiline editing={editing} onEdit={onEdit} original={prompt.compiled.lyrics} note={e.lyrics_note_fi} />
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldBlock name="exclude" label="Exclude" value={cur.exclude} support={support.exclude} multiline editing={editing} onEdit={onEdit} original={prompt.compiled.exclude} />
          <div className="rounded-lg border border-line bg-obsidian/50 px-3 py-2 text-xs">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="font-medium text-ink">Instrumental / Vocal</span>
              <span title={support.instrumental?.note_fi} className="rounded border border-ok/30 px-1.5 py-px font-mono text-[9.5px] tracking-wider text-ok uppercase">Suno-kenttä</span>
            </div>
            <div className="text-ink">{e.instrumental ? "Instrumental: päällä" : `Instrumental: pois · ${e.vocal}`}</div>
            <div className="mt-2 mb-1 flex items-center gap-2">
              <span className="font-medium text-ink">Suositellut asetukset</span>
              <span title={e.settings.note_fi} className="rounded border border-gold/30 px-1.5 py-px font-mono text-[9.5px] tracking-wider text-gold uppercase">Suositus</span>
            </div>
            <div className="font-mono text-muted">
              malli {e.settings.model} · weirdness {e.settings.weirdness}% · style influence {e.settings.style_influence}% · variety {e.settings.variety}
            </div>
          </div>
        </div>
        <FieldBlock name="creative_direction" label="Creative direction" value={cur.creative_direction} support={support.creative_direction} multiline editing={editing} onEdit={onEdit} original={prompt.compiled.creative_direction} />

        <details className="rounded-lg border border-line bg-obsidian/30 px-3 py-2" open>
          <summary className="cursor-pointer text-xs font-medium text-ink select-none">Perustelut ja epävarmuus</summary>
          <ul className="mt-2 flex flex-col gap-1.5 text-xs text-muted">
            {e.evidence_fi.map((x, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-violet-soft">●</span>
                {x}
              </li>
            ))}
          </ul>
          {e.experimental_hypotheses.length > 0 && (
            <div className="mt-3 text-xs">
              <div className="mb-1 flex items-center gap-2 text-ink">Testattava hypoteesi <CategoryBadge cat="interpretive" /></div>
              {e.experimental_hypotheses.map((h, i) => (
                <p key={i} className="font-mono text-[12px] text-cyan">{h}</p>
              ))}
            </div>
          )}
          <ul className="mt-3 flex flex-col gap-1.5 text-xs text-gold/90">
            {e.uncertainty_fi.map((x, i) => (
              <li key={i} className="flex gap-2">
                <span>△</span>
                {x}
              </li>
            ))}
          </ul>
          {e.target_summary.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <div className="eyebrow mb-1">Mitattavat tavoitteet (verrataan tulokseen)</div>
              <table className="w-full text-xs">
                <tbody>
                  {e.target_summary.map((t) => (
                    <tr key={t.feature} className="border-t border-line/50">
                      <td className="py-1 pr-2 text-muted">{t.label}</td>
                      <td className="py-1 pr-2 font-mono tabular">
                        {fmtFeature(defs[t.feature], t.feature, t.target)}
                        {t.feature !== "major_mode" && <span className="text-faint"> ± {fmtFeature(defs[t.feature], t.feature, t.tolerance).replace(/^0\.00$/, "0")}</span>}
                      </td>
                      <td className="py-1 pr-2 text-faint">{SOURCE_FI[t.source] ?? t.source}</td>
                      <td className="py-1">{(["observation", "preliminary", "supported", "insufficient"] as string[]).includes(t.evidence_level) ? <EvidenceBadge level={t.evidence_level as EvidenceLevel} /> : <span className="text-2xs text-cyan">oma säätö</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </details>

        <ErrorNote error={patch.error ?? dup.error} />
        <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
          {editing ? (
            <>
              <Button size="sm" variant="primary" onClick={saveEdits} loading={patch.isPending} disabled={!Object.keys(draft).length}>
                Tallenna muutokset
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setDraft({}); }}>
                Peruuta
              </Button>
            </>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              <Pencil className="size-3.5" /> Muokkaa
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => patch.mutate({ saved: !prompt.saved })}>
            {prompt.saved ? <BookmarkCheck className="size-3.5 text-gold" /> : <Bookmark className="size-3.5" />} {prompt.saved ? "Tallennettu" : "Tallenna"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => dup.mutate()} loading={dup.isPending}>
            <CopyIcon className="size-3.5" /> Monista
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setCompareOpen(true)}>
            <GitCompareArrows className="size-3.5" /> Vertaa versioita
          </Button>
          {Object.keys(prompt.edited || {}).length > 0 && (
            <Button size="sm" variant="ghost" onClick={() => patch.mutate({ edited: Object.fromEntries(Object.keys(prompt.edited).map((k) => [k, null])) })}>
              <RotateCcw className="size-3.5" /> Palauta alkuperäinen
            </Button>
          )}
          <a href={`/api/prompts/${prompt.id}/export?format=json`}>
            <Button size="sm" variant="ghost">
              <Download className="size-3.5" /> JSON
            </Button>
          </a>
          <a href={`/api/prompts/${prompt.id}/export?format=text`}>
            <Button size="sm" variant="ghost">
              <Download className="size-3.5" /> Teksti
            </Button>
          </a>
          <Button size="sm" className="ml-auto" onClick={() => setImportOpen(true)}>
            <FileUp className="size-3.5" /> Tuo Suno-tulos
          </Button>
        </div>
        <ProviderActions prompt={prompt} />
        {prompt.generated_assets && prompt.generated_assets.length > 0 && (
          <div className="text-xs text-muted">
            Liitetyt tulokset:{" "}
            {prompt.generated_assets.map((g) => (
              <Link key={g.id} to={`/tracks/${g.id}`} className="mr-2 text-gold hover:underline">
                {g.title}
              </Link>
            ))}
          </div>
        )}
      </div>

      <Modal open={compareOpen} onClose={() => setCompareOpen(false)} title="Vertaa versioita" wide>
        <label className="mb-4 flex items-center gap-2 text-sm">
          Vertaa:
          <select value={String(compareWith)} onChange={(ev) => setCompareWith(ev.target.value === "original" ? "original" : Number(ev.target.value))} className="h-9 rounded-lg border border-line bg-obsidian px-2 text-sm">
            <option value="original">Tämän kehotteen alkuperäinen versio</option>
            {compareCandidates.filter((c) => c.id !== prompt.id).map((c) => (
              <option key={c.id} value={c.id}>
                #{c.id} {c.effective.title} ({c.effective.mode_label})
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-3">
          {(["title", "hybrid_genre", "style", "lyrics", "exclude", "creative_direction"] as const).map((k) => {
            const a = String(left[k] ?? "");
            const b = String(e[k] ?? "");
            return (
              <div key={k} className="grid gap-2 sm:grid-cols-2">
                <div className={clsx("rounded-lg border px-3 py-2", a !== b ? "border-cyan/40" : "border-line")}>
                  <div className="eyebrow mb-1">{k} · {other ? `#${other.id}` : "alkuperäinen"}</div>
                  <pre className="font-mono text-[12px] whitespace-pre-wrap text-muted">{a || "–"}</pre>
                </div>
                <div className={clsx("rounded-lg border px-3 py-2", a !== b ? "border-gold/50" : "border-line")}>
                  <div className="eyebrow mb-1">{k} · #{prompt.id} nykyinen</div>
                  <pre className="font-mono text-[12px] whitespace-pre-wrap text-ink">{b || "–"}</pre>
                </div>
              </div>
            );
          })}
        </div>
      </Modal>
      <Modal open={importOpen} onClose={() => setImportOpen(false)} title={`Tuo tulos kehotteelle #${prompt.id}`}>
        <p className="mb-4 text-sm text-muted">
          Lataa Sunolla tällä kehotteella luotu kappale. Se analysoidaan, liitetään tähän kehotteeseen ja tavoitteita verrataan mitattuihin piirteisiin. Arvioi lopuksi oma kokemuksesi – se pidetään erillään
          teknisestä vastaavuudesta.
        </p>
        <Uploader promptId={prompt.id} compact onDone={() => qc.invalidateQueries({ queryKey: qk.experiments })} />
        <div className="mt-4 text-right">
          <Link to="/experiments" className="text-sm text-violet-soft hover:underline">
            Siirry kokeisiin →
          </Link>
        </div>
      </Modal>
    </article>
  );
}
