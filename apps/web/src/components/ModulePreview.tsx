import { CheckCircle2, Circle } from "lucide-react";
import type { ReactNode } from "react";
import { PageHeader, Panel } from "@/components/ui";

/** Intentional, truthful preview for modules that are not implemented yet. */
export function ModulePreview({ eyebrow, icon, title, tagline, description, planned, foundations, phase }: { eyebrow: string; icon: ReactNode; title: string; tagline: string; description: string; planned: string[]; foundations: string[]; phase: string }) {
  return (
    <div>
      <PageHeader eyebrow={eyebrow} icon={icon} title={title} description={tagline} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Panel>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/5 px-3 py-1 text-xs text-gold">Ei vielä toteutettu · {phase}</div>
          <p className="text-sm text-muted">{description}</p>
          <div className="eyebrow mt-6 mb-3">Suunnitellut toiminnot</div>
          <ul className="flex flex-col gap-2">
            {planned.map((p) => (
              <li key={p} className="flex items-start gap-2 text-sm text-muted">
                <Circle className="mt-1 size-3 shrink-0 text-faint" />
                {p}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel eyebrow="Jo valmiina pohjaksi">
          <ul className="flex flex-col gap-2">
            {foundations.map((p) => (
              <li key={p} className="flex items-start gap-2 text-sm text-ink">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" />
                {p}
              </li>
            ))}
          </ul>
          <p className="mt-5 text-2xs text-faint">Tämä näkymä ei sisällä toimimattomia säätimiä eikä esimerkkidataa. Toteutusjärjestys: docs/PRODUCT_ROADMAP.md.</p>
        </Panel>
      </div>
    </div>
  );
}
