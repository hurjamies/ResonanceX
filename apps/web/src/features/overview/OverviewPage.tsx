import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button, EvidenceBadge, Panel, Spinner, Stat } from "@/components/ui";
import { ResonanceField } from "@/components/ResonanceField";
import { ResonanceMark } from "@/design-system/brand";
import { api, qk, useProfile } from "@/services/api";
import { fmtDate, STAGE_FI } from "@/services/format";
import { InsightCard } from "@/features/sonic-dna/InsightCard";

export default function OverviewPage() {
  const ov = useQuery({ queryKey: qk.overview, queryFn: api.overview, refetchInterval: (q) => (q.state.data?.incomplete.some((i) => i.status !== "failed") ? 2000 : false) });
  const profile = useProfile();
  const nav = useNavigate();
  if (ov.isLoading || !ov.data) return <Spinner />;
  const o = ov.data;
  const pts = profile.data?.field.points ?? [];
  const pcaReady = pts.length >= 3 && pts.every((p) => p.pca);

  return (
    <div className="flex flex-col gap-5">
      {/* hero */}
      <section className="panel relative overflow-hidden">
        <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="flex flex-col justify-center">
            <div className="mb-4 flex items-center gap-3">
              <ResonanceMark size={40} />
              <div className="eyebrow">Personal Resonance Intelligence</div>
            </div>
            <h1 className="text-3xl leading-tight font-semibold sm:text-4xl">
              Decode what <span className="bg-gradient-to-r from-violet-soft via-lavender to-cyan bg-clip-text text-transparent">moves you.</span>
            </h1>
            <p className="mt-3 max-w-md text-sm text-muted">Tutki, mitkä äänen ominaisuudet koskettavat juuri sinua – ja muunna ymmärrys uusiksi luoviksi kokeiluiksi.</p>
            <div className="mt-6 rounded-xl border border-violet/30 bg-violet/5 p-4">
              <div className="eyebrow mb-1 text-violet-soft">Suositeltu seuraava askel</div>
              <div className="font-display text-lg">{o.next_action.title}</div>
              <p className="mt-1 text-sm text-muted">{o.next_action.description}</p>
              <Button variant="primary" size="sm" className="mt-3" onClick={() => nav(o.next_action.href)}>
                Jatka <ArrowRight className="size-3.5" />
              </Button>
            </div>
          </div>
          <div>
            {pcaReady ? (
              <ResonanceField
                data={pts.map((p) => ({ id: p.asset_id, x: p.pca![0], y: p.pca![1], intensity: p.resonance_score, label: p.title ?? "–", sublabel: p.artist ?? undefined, origin: p.origin }))}
                height={320}
                onSelect={(id) => nav(`/tracks/${id}`)}
                caption="Resonance Field: kappaleet SonicDNA-piirreavaruudessa (PCA), aallot omista arvioistasi."
              />
            ) : (
              <div className="grid h-[320px] place-items-center rounded-xl border border-dashed border-line-strong bg-obsidian/50 p-6 text-center">
                <div>
                  <div className="mx-auto mb-4 w-fit opacity-60">
                    <ResonanceMark size={56} />
                  </div>
                  <div className="font-display text-ink">Resonance Field odottaa havaintoja</div>
                  <p className="mt-1 max-w-xs text-xs text-muted">Kenttä piirretään, kun vähintään kolme kappaletta on analysoitu. Siihen ei lisätä keksittyä dataa.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      <Panel>
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Analysoitu" value={o.counts.tracks_analyzed ?? 0} />
          <Stat label="Arvioitu" value={o.counts.tracks_rated ?? 0} accent="gold" />
          <Stat label="Hetkimerkinnät" value={o.counts.markers ?? 0} />
          <Stat label="Kehotteet" value={o.counts.prompts} accent="violet" />
          <Stat label="Kokeet" value={o.counts.experiments} accent="cyan" />
          <Stat label="Profiili" value={o.profile_version ? `v${o.profile_version}` : "–"} hint={o.data_stage === "empty" ? "ei aineistoa" : o.data_stage === "collecting" ? "kerätään" : o.data_stage === "preliminary" ? "alustava" : "kehittyvä"} />
        </div>
      </Panel>

      {o.incomplete.length > 0 && (
        <Panel eyebrow="Analyysijono" title="Keskeneräiset analyysit">
          <ul className="flex flex-col gap-2 text-sm">
            {o.incomplete.map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-3">
                <Link to={`/tracks/${i.id}`} className="truncate hover:text-violet-soft">
                  {i.title}
                </Link>
                <span className={i.status === "failed" ? "text-xs text-danger" : "flex items-center gap-1.5 text-xs text-violet-soft"}>
                  {i.status === "failed" ? `Epäonnistui: ${i.error}` : <><Loader2 className="size-3 animate-spin" /> {STAGE_FI[i.stage ?? ""] ?? "Jonossa"}</>}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel eyebrow="Resonance Core" title="Viimeisimmät havainnot" actions={<Link to="/sonic-dna" className="text-xs text-violet-soft hover:underline">Koko profiili →</Link>}>
          {o.insights.length === 0 ? (
            <p className="text-sm text-muted">Havaintoja syntyy, kun olet arvioinut vähintään neljä kappaletta. Arvioi myös kappaleita, jotka eivät kosketa – vertailu tarvitsee molempia.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {o.insights.map((ins) => (
                <InsightCard key={ins.id} ins={ins} />
              ))}
            </div>
          )}
        </Panel>
        <div className="flex flex-col gap-5">
          {o.summary_lines.length > 0 && (
            <Panel eyebrow="SonicDNA" title="Vahvimmat taipumukset">
              <ul className="flex flex-col gap-2">
                {o.summary_lines.slice(0, 4).map((l) => (
                  <li key={l.feature} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    {l.text}
                    <EvidenceBadge level={l.evidence_level} />
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <Panel eyebrow="Prompt Studio" title="Viimeisimmät kehotteet" actions={<Link to="/prompt-studio" className="text-xs text-violet-soft hover:underline">Avaa →</Link>}>
            {o.recent_prompts.length === 0 ? (
              <p className="text-sm text-muted">Ei vielä kehotteita.</p>
            ) : (
              <ul className="flex flex-col gap-2.5">
                {o.recent_prompts.map((p) => (
                  <li key={p.id} className="rounded-lg border border-line px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm">{p.title}</span>
                      <span className="shrink-0 text-2xs text-faint">{p.mode_label}</span>
                    </div>
                    <div className="mt-0.5 truncate font-mono text-[11px] text-muted">{p.style}</div>
                    <div className="mt-0.5 text-2xs text-faint">{fmtDate(p.created_at)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel eyebrow="Palautesilmukka" title="Kokeet" actions={<Link to="/experiments" className="text-xs text-violet-soft hover:underline">Avaa →</Link>}>
            {o.recent_experiments.length === 0 ? (
              <p className="text-sm text-muted">Ei vielä Suno-tuloksia.</p>
            ) : (
              <ul className="flex flex-col gap-1.5 text-sm">
                {o.recent_experiments.map((e) => (
                  <li key={e.id} className="flex justify-between">
                    <Link to={`/tracks/${e.asset_id}`} className="hover:text-violet-soft">
                      Koe #{e.id}
                    </Link>
                    <span className="font-mono text-xs text-cyan">{e.score !== null ? `${Math.round(e.score * 100)} % vastaavuus` : "–"}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
