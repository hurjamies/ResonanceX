import { ChevronDown, FlaskConical } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CategoryBadge, EvidenceBadge } from "@/components/ui";
import { fmtDate, fmtTime } from "@/services/format";
import type { Insight } from "@/types/api";

const KIND_CAT: Record<string, "statistical" | "self_reported" | "interpretive"> = {
  consistency: "statistical",
  association: "statistical",
  markers: "statistical",
  pairwise: "statistical",
  divergence: "self_reported",
  negative: "statistical",
};

export function InsightCard({ ins, defaultOpen = false }: { ins: Insight; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <article className="rounded-xl border border-line bg-obsidian/40 transition-colors hover:border-line-strong">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-3 p-4 text-left" aria-expanded={open}>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <EvidenceBadge level={ins.evidence_level} />
            <CategoryBadge cat={KIND_CAT[ins.kind] ?? "interpretive"} />
          </div>
          <h3 className="font-display text-[15px] font-medium text-ink">{ins.title}</h3>
          <p className="mt-1 text-sm text-muted">{ins.explanation}</p>
        </div>
        <ChevronDown className={`mt-1 size-4 shrink-0 text-faint transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-line px-4 pt-3 pb-4 text-sm">
          {ins.supporting_tracks.length > 0 && (
            <div className="mb-3">
              <div className="eyebrow mb-1.5">Tukevat havainnot</div>
              <ul className="flex flex-col gap-1">
                {ins.supporting_tracks.map((t) => (
                  <li key={`s${t.asset_id}${t.role ?? ""}`} className="flex items-center justify-between gap-3">
                    <Link to={`/tracks/${t.asset_id}`} className="truncate text-ink hover:text-violet-soft">
                      {t.title}
                      {t.origin === "generated" && <span className="ml-1.5 text-2xs text-gold">Suno</span>}
                    </Link>
                    <span className="shrink-0 font-mono text-xs text-muted tabular">
                      {t.value_label ?? ""}
                      {t.rating !== undefined ? ` · arvio ${t.rating.toFixed(1)}` : t.resonance_score !== null ? ` · resonanssi ${t.resonance_score.toFixed(1)}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ins.contrasting_tracks.length > 0 && (
            <div className="mb-3">
              <div className="eyebrow mb-1.5">Vastaesimerkit ja vertailu</div>
              <ul className="flex flex-col gap-1">
                {ins.contrasting_tracks.map((t) => (
                  <li key={`c${t.asset_id}${t.role ?? ""}`} className="flex items-center justify-between gap-3">
                    <Link to={`/tracks/${t.asset_id}`} className="truncate text-muted hover:text-ink">
                      {t.title}
                      {t.role === "top_outside" && <span className="ml-1.5 text-2xs text-gold">voimakas, mutta poikkeaa</span>}
                      {t.role === "rest_inside" && <span className="ml-1.5 text-2xs text-faint">heikompi, mutta samalla alueella</span>}
                    </Link>
                    <span className="shrink-0 font-mono text-xs text-faint tabular">
                      {t.value_label ?? ""}
                      {t.rating !== undefined ? ` · arvio ${t.rating.toFixed(1)}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ins.timestamps.length > 0 && (
            <div className="mb-3">
              <div className="eyebrow mb-1.5">Hetket</div>
              <div className="flex flex-wrap gap-1.5">
                {ins.timestamps.map((t, i) => (
                  <Link key={i} to={`/tracks/${t.asset_id}?t=${t.time}`} className="rounded-full border border-line px-2 py-0.5 text-2xs text-muted hover:border-cyan hover:text-ink">
                    {t.title} · <span className="font-mono text-cyan">{fmtTime(t.time)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          <details className="mb-3 text-xs text-faint">
            <summary className="cursor-pointer select-none">Tilastolliset tiedot</summary>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-obsidian p-3 font-mono text-[11px] text-muted">{JSON.stringify(ins.evidence, null, 2)}</pre>
          </details>
          {ins.suggested_experiment && (
            <div className="flex items-start gap-2 rounded-lg bg-violet/8 px-3 py-2 text-xs text-violet-soft">
              <FlaskConical className="mt-0.5 size-3.5 shrink-0" />
              <span>{ins.suggested_experiment}</span>
            </div>
          )}
          <div className="mt-3 text-2xs text-faint">
            Luotu {fmtDate(ins.generated_at)} · {ins.core_version} · {ins.analysis_version}
          </div>
        </div>
      )}
    </article>
  );
}
