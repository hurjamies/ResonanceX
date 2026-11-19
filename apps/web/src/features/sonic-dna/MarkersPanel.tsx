import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MapPin, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, CategoryBadge, Chip, ErrorNote, Panel } from "@/components/ui";
import { api, qk, useInvalidateDerived, useVocabulary } from "@/services/api";
import { fmtTime } from "@/services/format";
import { usePlayer } from "@/stores/player";
import type { Marker } from "@/types/api";
import { MARKER_COLORS, MARKER_FI } from "./timeline";

/** Timeline markers: exact moments or intervals the user found significant. */
export function MarkersPanel({ assetId, markers }: { assetId: number; markers: Marker[] }) {
  const vocab = useVocabulary();
  const qc = useQueryClient();
  const inv = useInvalidateDerived();
  const currentTime = usePlayer((s) => s.currentTime);
  const selection = usePlayer((s) => s.selection);
  const seek = usePlayer((s) => s.seek);
  const [label, setLabel] = useState("chills");
  const [note, setNote] = useState("");
  const [intensity, setIntensity] = useState<number | null>(null);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: qk.markers(assetId) });
    inv();
  };
  const create = useMutation({
    mutationFn: () =>
      api.createMarker(assetId, {
        start_seconds: Math.round((selection ? selection.start : currentTime) * 100) / 100,
        end_seconds: selection ? Math.round(selection.end * 100) / 100 : null,
        label,
        intensity,
        note: note.trim() || null,
      }),
    onSuccess: () => {
      setNote("");
      refresh();
    },
  });
  const del = useMutation({ mutationFn: (id: number) => api.deleteMarker(id), onSuccess: refresh });

  return (
    <Panel eyebrow={<span className="flex items-center gap-2">Hetkimerkinnät <CategoryBadge cat="self_reported" /></span>} title="Merkitse merkitykselliset hetket">
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted">
          Merkintä tehdään toistokohtaan <span className="font-mono text-ink">{fmtTime(currentTime, true)}</span>
          {selection && (
            <>
              {" "}
              tai valitulle välille <span className="font-mono text-cyan">{fmtTime(selection.start, true)}–{fmtTime(selection.end, true)}</span>
            </>
          )}
          . Vedä aikajanalla valitaksesi välin.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {(vocab.data?.markers ?? []).map((m) => (
            <Chip key={m.key} active={label === m.key} onClick={() => setLabel(m.key)}>
              <span className="mr-1.5 inline-block size-2 rounded-full" style={{ background: MARKER_COLORS[m.key] }} />
              {m.label}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Muistiinpano (valinnainen)" aria-label="Muistiinpano" className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-obsidian/60 px-3 text-sm focus:border-violet/60 focus:outline-none" />
          <label className="flex items-center gap-2 text-xs text-muted">
            Voimakkuus
            <select value={intensity ?? ""} onChange={(e) => setIntensity(e.target.value === "" ? null : Number(e.target.value))} className="h-9 rounded-lg border border-line bg-obsidian px-2 text-sm text-ink">
              <option value="">–</option>
              {Array.from({ length: 11 }, (_, i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </label>
          <Button variant="primary" size="sm" className="h-9" loading={create.isPending} onClick={() => create.mutate()}>
            <MapPin className="size-3.5" /> Merkitse
          </Button>
        </div>
        <ErrorNote error={create.error} />
        {markers.length > 0 && (
          <ul className="mt-1 divide-y divide-line rounded-lg border border-line">
            {markers.map((m) => (
              <li key={m.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                <span className="size-2.5 shrink-0 rounded-full" style={{ background: MARKER_COLORS[m.label] }} />
                <button onClick={() => seek(m.start_seconds)} className="font-mono text-xs text-cyan tabular hover:underline">
                  {fmtTime(m.start_seconds, true)}
                  {m.end_seconds ? `–${fmtTime(m.end_seconds, true)}` : ""}
                </button>
                <span className="min-w-0 flex-1 truncate">
                  {MARKER_FI[m.label]}
                  {m.intensity !== null && <span className="text-muted"> · {m.intensity}/10</span>}
                  {m.note && <span className="text-muted"> · {m.note}</span>}
                </span>
                <button onClick={() => del.mutate(m.id)} className="rounded p-1 text-faint hover:text-danger" aria-label="Poista merkintä">
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}
