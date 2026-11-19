import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, CategoryBadge, Chip, ErrorNote, Panel, RatingSlider, Spinner, Tabs } from "@/components/ui";
import { api, qk, useInvalidateDerived, useVocabulary } from "@/services/api";
import { fmtDate } from "@/services/format";
import type { Rating } from "@/types/api";

type Draft = Omit<Rating, "asset_id" | "updated_at" | "exists">;
const PRIMARY = ["preference", "bodily_resonance", "movement", "emotional_intensity", "immersion"];

/** Song-level experience: dimensions, bodily responses, reflections and context. */
export function RatingPanel({ assetId }: { assetId: number }) {
  const vocab = useVocabulary();
  const qc = useQueryClient();
  const inv = useInvalidateDerived();
  const rating = useQuery({ queryKey: qk.rating(assetId), queryFn: () => api.rating(assetId) });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [tab, setTab] = useState<"exp" | "body" | "text" | "ctx">("exp");
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    if (rating.data && !dirty) {
      setDraft({ dimensions: rating.data.dimensions, body_responses: rating.data.body_responses, reflections: rating.data.reflections, context: rating.data.context });
      setSavedAt(rating.data.updated_at);
    }
  }, [rating.data, dirty]);

  const save = useMutation({
    mutationFn: (d: Draft) => api.putRating(assetId, d),
    onSuccess: (r) => {
      qc.setQueryData(qk.rating(assetId), r);
      setDirty(false);
      setSavedAt(r.updated_at);
      inv();
      qc.invalidateQueries({ queryKey: qk.asset(assetId) });
    },
  });

  if (!draft || !vocab.data) return <Panel title="Kokemuksesi"><Spinner /></Panel>;
  const v = vocab.data;
  const upd = (fn: (d: Draft) => Draft) => {
    setDraft((d) => (d ? fn(d) : d));
    setDirty(true);
  };
  const setDim = (k: string, val: number | null) => upd((d) => ({ ...d, dimensions: { ...d.dimensions, [k]: val } }));
  const nSet = Object.values(draft.dimensions).filter((x) => x !== null && x !== undefined).length;

  return (
    <Panel
      eyebrow={<span className="flex items-center gap-2">Kokemuksesi <CategoryBadge cat="self_reported" /></span>}
      title="Miten tämä musiikki vaikuttaa sinuun?"
      actions={
        <Button variant={dirty ? "primary" : "secondary"} size="sm" loading={save.isPending} disabled={!dirty} onClick={() => save.mutate(draft)}>
          {dirty ? "Tallenna" : <><Check className="size-3.5" /> Tallennettu</>}
        </Button>
      }
    >
      <Tabs
        className="mb-4"
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "exp", label: `Kokemus ${nSet ? `(${nSet})` : ""}` },
          { key: "body", label: `Keho ${draft.body_responses.length ? `(${draft.body_responses.length})` : ""}` },
          { key: "text", label: "Pohdinta" },
          { key: "ctx", label: "Konteksti" },
        ]}
      />
      {tab === "exp" && (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-muted">Asteikko 0–10. Jätä merkityksettömät ulottuvuudet arvioimatta. Mieltymys ja vaikuttavuus ovat eri asioita – arvioi ne erikseen.</p>
          {v.dimensions.filter((d) => PRIMARY.includes(d.key)).map((d) => (
            <RatingSlider key={d.key} label={d.label} hint={d.hint} value={draft.dimensions[d.key]} onChange={(x) => setDim(d.key, x)} />
          ))}
          <details className="group">
            <summary className="cursor-pointer text-xs text-violet-soft select-none">Tunnesävyt ja merkitys ({v.dimensions.length - PRIMARY.length})</summary>
            <div className="mt-4 flex flex-col gap-4">
              {v.dimensions.filter((d) => !PRIMARY.includes(d.key)).map((d) => (
                <RatingSlider key={d.key} label={d.label} hint={d.hint} value={draft.dimensions[d.key]} onChange={(x) => setDim(d.key, x)} />
              ))}
            </div>
          </details>
        </div>
      )}
      {tab === "body" && (
        <div>
          <p className="mb-3 text-xs text-muted">Itse raportoituja tuntemuksia – eivät fysiologisia mittauksia.</p>
          <div className="flex flex-wrap gap-2">
            {v.body_responses.map((b) => {
              const on = draft.body_responses.includes(b.key);
              return (
                <Chip key={b.key} active={on} onClick={() => upd((d) => ({ ...d, body_responses: on ? d.body_responses.filter((x) => x !== b.key) : [...d.body_responses, b.key] }))}>
                  {b.label}
                </Chip>
              );
            })}
          </div>
        </div>
      )}
      {tab === "text" && (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-muted">Kirjoitetut kuvaukset tallennetaan paikallisesti eikä niitä lähetetä minnekään.</p>
          {v.reflections.map((r) => (
            <label key={r.key} className="block">
              <span className="mb-1 block text-sm text-ink">{r.label}</span>
              <textarea
                rows={3}
                value={draft.reflections[r.key] ?? ""}
                onChange={(e) => upd((d) => ({ ...d, reflections: { ...d.reflections, [r.key]: e.target.value } }))}
                className="w-full resize-y rounded-lg border border-line bg-obsidian/60 px-3 py-2 text-sm focus:border-violet/60 focus:outline-none"
              />
            </label>
          ))}
        </div>
      )}
      {tab === "ctx" && (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-muted">Valinnainen. Kuuntelutilanne voi vaikuttaa kokemukseen.</p>
          {Object.entries(v.context).map(([field, opts]) => (
            <div key={field}>
              <div className="mb-1.5 text-sm">{CTX_FI[field] ?? field}</div>
              <div className="flex flex-wrap gap-2">
                {opts.map((o) => (
                  <Chip key={o.key} active={draft.context[field] === o.key} onClick={() => upd((d) => ({ ...d, context: { ...d.context, [field]: d.context[field] === o.key ? null : o.key } }))}>
                    {o.label}
                  </Chip>
                ))}
              </div>
            </div>
          ))}
          <label className="block">
            <span className="mb-1 block text-sm">Mieliala</span>
            <input value={(draft.context.mood as string) ?? ""} onChange={(e) => upd((d) => ({ ...d, context: { ...d.context, mood: e.target.value || null } }))} className="h-9 w-full rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm">Arvioinnin päivä</span>
            <input type="date" value={(draft.context.assessed_on as string) ?? ""} onChange={(e) => upd((d) => ({ ...d, context: { ...d.context, assessed_on: e.target.value || null } }))} className="h-9 rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
          </label>
        </div>
      )}
      <ErrorNote error={save.error} />
      {savedAt && <p className="mt-4 text-2xs text-faint">Viimeksi tallennettu {fmtDate(savedAt)} · aiemmat versiot säilytetään historiassa</p>}
    </Panel>
  );
}

const CTX_FI: Record<string, string> = { playback: "Toisto", volume: "Äänenvoimakkuus", familiarity: "Tuttuus", environment: "Ympäristö" };
