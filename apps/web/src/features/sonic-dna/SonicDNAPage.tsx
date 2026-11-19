import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Download, FlaskConical, GitCompare, HelpCircle, MapPin, Star, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, CategoryBadge, Empty, EvidenceBadge, PageHeader, Panel, Spinner, Stat } from "@/components/ui";
import { ResonanceField } from "@/components/ResonanceField";
import { SonicIcon } from "@/design-system/brand";
import { api, useProfile, useVocabulary } from "@/services/api";
import { fmtDate, fmtFeature } from "@/services/format";
import type { Profile } from "@/types/api";
import { InsightCard } from "./InsightCard";

const STAGE_FI: Record<Profile["data_stage"], { label: string; text: string }> = {
  empty: { label: "Ei aineistoa", text: "Tuo ja arvioi kappaleita. Profiilia ei muodosteta ilman havaintoja." },
  collecting: { label: "Kerätään havaintoja", text: "Alle 4 arvioitua kappaletta. Näytetään vain kuvailevia havaintoja – ei vielä hypoteeseja." },
  preliminary: { label: "Alustava profiili", text: "4–7 arvioitua kappaletta. Ensimmäiset vertailut ovat mahdollisia, mutta havainnot ovat alustavia." },
  developing: { label: "Kehittyvä profiili", text: "8+ arvioitua kappaletta. Tilastolliset testit (permutaatio, FDR, bootstrap) alkavat erottaa toistuvia yhteyksiä." },
};

function FieldExplorer({ profile }: { profile: Profile }) {
  const vocab = useVocabulary();
  const nav = useNavigate();
  const feats = (vocab.data?.features ?? []).filter((f) => f.in_profile);
  const hasPca = !!profile.field.pca && profile.field.points.every((p) => p.pca);
  const [x, setX] = useState<string>(hasPca ? "pca" : "tempo_bpm");
  const [y, setY] = useState<string>("bass_ratio");
  const [colorBy, setColorBy] = useState<string>("resonance");
  const data = useMemo(
    () =>
      profile.field.points
        .filter((p) => (x === "pca" ? p.pca : p.features[x] !== null && p.features[y] !== null))
        .map((p) => ({
          id: p.asset_id,
          x: x === "pca" ? p.pca![0] : (p.features[x] as number),
          y: x === "pca" ? p.pca![1] : (p.features[y] as number),
          intensity: colorBy === "resonance" ? p.resonance_score : (p.ratings[colorBy] ?? null),
          label: p.title ?? "–",
          sublabel: p.artist ?? undefined,
          origin: p.origin,
        })),
    [profile, x, y, colorBy],
  );
  const lbl = (k: string) => feats.find((f) => f.key === k)?.label ?? k;
  const pca = profile.field.pca;
  return (
    <Panel
      eyebrow={<span className="flex items-center gap-2">Resonance Field <CategoryBadge cat="measured" /> <CategoryBadge cat="self_reported" /></span>}
      title="Kokemuksesi piirreavaruudessa"
      actions={
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select value={x} onChange={(e) => setX(e.target.value)} aria-label="Vaaka-akseli" className="h-8 rounded-lg border border-line bg-obsidian px-2 text-ink">
            {hasPca && <option value="pca">PCA (kaikki piirteet)</option>}
            {feats.map((f) => (
              <option key={f.key} value={f.key}>
                X: {f.label}
              </option>
            ))}
          </select>
          {x !== "pca" && (
            <select value={y} onChange={(e) => setY(e.target.value)} aria-label="Pystyakseli" className="h-8 rounded-lg border border-line bg-obsidian px-2 text-ink">
              {feats.map((f) => (
                <option key={f.key} value={f.key}>
                  Y: {f.label}
                </option>
              ))}
            </select>
          )}
          <select value={colorBy} onChange={(e) => setColorBy(e.target.value)} aria-label="Aaltojen voimakkuus" className="h-8 rounded-lg border border-line bg-obsidian px-2 text-ink">
            <option value="resonance">Aallot: resonanssipistemäärä</option>
            {(vocab.data?.dimensions ?? []).map((d) => (
              <option key={d.key} value={d.key}>
                Aallot: {d.label}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {data.length < 2 ? (
        <Empty title="Kenttä täyttyy havainnoista">Tarvitaan vähintään kaksi analysoitua kappaletta. Kenttään ei lisätä keksittyjä pisteitä.</Empty>
      ) : (
        <ResonanceField
          data={data}
          height={380}
          onSelect={(id) => nav(`/tracks/${id}`)}
          xLabel={x === "pca" ? `PC1 (${Math.round((pca?.explained_variance[0] ?? 0) * 100)} %)` : lbl(x)}
          yLabel={x === "pca" ? `PC2 (${Math.round((pca?.explained_variance[1] ?? 0) * 100)} %)` : lbl(y)}
          caption={
            x === "pca"
              ? `Sijainti: pääkomponenttiprojektio robustisti standardoiduista SonicDNA-piirteistä. PC1 painottuu: ${pca?.loadings[0]?.slice(0, 3).map((l) => l.label.toLowerCase()).join(", ")}. Aallot: oma arviosi. Valkoinen = kirjasto, kulta = Suno-tulos, harmaa = arvioimatta. Kyseessä on piirreavaruus – ei kartta tietoisuudesta tai tunteista.`
              : "Sijainti: valitut mitatut/arvioidut piirteet. Aallot: oma arviosi. Valkoinen = kirjasto, kulta = Suno-tulos, harmaa = arvioimatta. Piirreavaruus – ei kartta tietoisuudesta."
          }
        />
      )}
    </Panel>
  );
}

function TargetTable({ profile }: { profile: Profile }) {
  const vocab = useVocabulary();
  const feats = profile.targets.features.filter((f) => f.direction !== "typical").slice(0, 10);
  const defs = Object.fromEntries((vocab.data?.features ?? []).map((f) => [f.key, f]));
  if (profile.targets.basis === "none") return <p className="text-sm text-muted">Voimakkaimpien kokemusten ryhmää ei voi vielä muodostaa: tarvitaan vähintään kolme arvioitua kappaletta, joista osa on arvioitu vähintään 5/10.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-2xs text-faint">
            <th className="pb-2 font-normal">Piirre</th>
            <th className="pb-2 font-normal">Voimakkaimmat</th>
            <th className="pb-2 font-normal">Kirjasto</th>
            <th className="pb-2 font-normal">Poikkeama</th>
            <th className="pb-2 font-normal">Näyttö</th>
          </tr>
        </thead>
        <tbody>
          {feats.map((f) => (
            <tr key={f.feature} className="border-t border-line/70">
              <td className="py-2 pr-3">{f.label}</td>
              <td className="py-2 pr-3 font-mono text-xs tabular">{fmtFeature(defs[f.feature], f.feature, f.median)}</td>
              <td className="py-2 pr-3 font-mono text-xs text-muted tabular">{fmtFeature(defs[f.feature], f.feature, f.library_median)}</td>
              <td className="py-2 pr-3">
                <div className="relative h-2 w-28 rounded-full bg-surface">
                  <div className="absolute top-0 left-1/2 h-2 w-px bg-line-strong" />
                  <div className={`absolute top-0 h-2 rounded-full ${f.z > 0 ? "bg-violet" : "bg-cyan"}`} style={{ left: f.z > 0 ? "50%" : `${50 + Math.max(-50, (f.z / 2.5) * 50)}%`, width: `${Math.min(50, (Math.abs(f.z) / 2.5) * 50)}%` }} />
                </div>
              </td>
              <td className="py-2">
                <EvidenceBadge level={f.evidence_level} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-2xs text-faint">
        Poikkeama = voimakkaimpien kokemusten mediaani robusteina z-arvoina suhteessa koko kirjastoosi (n = {profile.targets.tracks.length} kappaletta). Näytön taso kertoo, onko piirre yhteydessä arvioihisi
        myös tilastollisesti.
      </p>
    </div>
  );
}

const EXP_ICON = { pairwise: GitCompare, rate: Star, marker: MapPin, upload: Upload } as const;

export default function SonicDNAPage() {
  const profile = useProfile();
  const history = useQuery({ queryKey: ["profile-history"], queryFn: api.profileHistory });
  if (profile.isLoading) return <Spinner />;
  if (!profile.data) return null;
  const p = profile.data;
  const stage = STAGE_FI[p.data_stage];

  return (
    <div>
      <PageHeader
        eyebrow="SonicDNA · Discover your sonic fingerprint"
        icon={<SonicIcon size={14} />}
        title="Henkilökohtainen SonicDNA"
        description="Profiili muodostetaan mitatuista piirteistä ja omista arvioistasi läpinäkyvillä menetelmillä. Jokainen havainto on jäljitettävissä kappaleisiin – eikä korrelaatio ole syy-yhteys."
        actions={
          <>
            <Link to="/sonic-dna/compare">
              <Button>
                <GitCompare className="size-4" /> Pareittaisvertailu
              </Button>
            </Link>
            <a href="/api/export/profile.json">
              <Button variant="ghost">
                <Download className="size-4" /> Vie JSON
              </Button>
            </a>
          </>
        }
      />

      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat label="Profiiliversio" value={p.version ? `v${p.version}` : "–"} hint={p.snapshot_created_at ? fmtDate(p.snapshot_created_at) : "ei vielä"} accent="violet" />
            <Stat label="Analysoitu" value={p.counts.tracks_analyzed} hint={`${p.counts.generated_tracks} Suno-tulosta`} />
            <Stat label="Arvioitu" value={p.counts.tracks_rated} hint={`${p.counts.markers} hetkimerkintää`} accent="gold" />
            <Stat label="Vertailut" value={p.counts.comparisons} hint={`${p.associations_tested} testattua yhteyttä`} accent="cyan" />
          </div>
        </Panel>
        <Panel>
          <div className="eyebrow mb-1">Aineiston vaihe</div>
          <div className="font-display text-lg text-ink">{stage.label}</div>
          <p className="mt-1 text-xs text-muted">{stage.text}</p>
        </Panel>
      </div>

      {p.data_stage === "empty" ? (
        <Panel>
          <Empty title="Profiilia ei ole vielä" icon={<SonicIcon size={30} />} action={<Link to="/library"><Button variant="primary">Siirry kirjastoon</Button></Link>}>
            SonicDNA ei keksi profiilia. Se syntyy, kun tuot kappaleita ja arvioit kokemuksesi.
          </Empty>
        </Panel>
      ) : (
        <div className="flex flex-col gap-5">
          {p.summary_lines.length > 0 && (
            <Panel eyebrow="Profiilin yhteenveto" title="Voimakkaimpien kokemustesi taipumukset">
              <ul className="flex flex-col gap-2.5">
                {p.summary_lines.map((l) => (
                  <li key={l.feature} className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm text-ink">{l.text}</span>
                    <EvidenceBadge level={l.evidence_level} />
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-2xs text-faint">{p.group_definition.description}</p>
            </Panel>
          )}

          <FieldExplorer profile={p} />

          <div className="grid gap-5 xl:grid-cols-2">
            <Panel eyebrow="Resonance Core" title={`Havainnot (${p.insights.length})`}>
              {p.insights.length === 0 ? (
                <p className="text-sm text-muted">
                  Ei vielä näyttöön perustuvia havaintoja. {p.counts.tracks_rated < 4 ? "Arvioi vähintään neljä kappaletta – myös sellaisia, jotka eivät vaikuta sinuun." : "Lisää arvioita ja vertailuja tarvitaan."}
                </p>
              ) : (
                <div className="flex flex-col gap-3">
                  {p.insights.map((ins, i) => (
                    <InsightCard key={ins.id} ins={ins} defaultOpen={i === 0} />
                  ))}
                </div>
              )}
            </Panel>
            <div className="flex flex-col gap-5">
              <Panel eyebrow="Profiili vs. kirjasto" title="Voimakkaimpien kokemusten piirteet">
                <TargetTable profile={p} />
              </Panel>
              <Panel eyebrow="Aktiivinen oppiminen" title="Ehdotetut seuraavat kokeet">
                {p.suggested_experiments.length === 0 ? (
                  <p className="text-sm text-muted">Ei ehdotuksia juuri nyt.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {p.suggested_experiments.map((e, i) => {
                      const Icon = EXP_ICON[e.kind] ?? FlaskConical;
                      const href = e.kind === "pairwise" && e.asset_ids.length === 2 ? `/sonic-dna/compare?a=${e.asset_ids[0]}&b=${e.asset_ids[1]}&suggested=1` : e.asset_ids.length ? `/tracks/${e.asset_ids[0]}` : "/library";
                      return (
                        <li key={i}>
                          <Link to={href} className="group flex items-start gap-3 rounded-lg border border-line p-3 hover:border-violet/50">
                            <Icon className="mt-0.5 size-4 shrink-0 text-violet-soft" />
                            <div className="min-w-0 flex-1">
                              <div className="text-sm text-ink">{e.title}</div>
                              <div className="mt-0.5 text-xs text-muted">{e.description}</div>
                            </div>
                            <ArrowRight className="mt-0.5 size-4 shrink-0 text-faint group-hover:text-ink" />
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Panel>
              {p.hypotheses.length > 0 && (
                <Panel eyebrow={<span className="flex items-center gap-2">Avoimet kysymykset <CategoryBadge cat="interpretive" /></span>} title="Hypoteesit">
                  <ul className="flex flex-col gap-2">
                    {p.hypotheses.map((h) => (
                      <li key={h.id} className="flex items-start gap-2 text-sm">
                        <HelpCircle className="mt-0.5 size-4 shrink-0 text-gold" />
                        <span className="text-muted">{h.statement}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              )}
              {p.contradictions.length > 0 && (
                <Panel eyebrow="Vastaesimerkit" title="Kappaleet, jotka eivät noudata taipumuksia">
                  <ul className="flex flex-col gap-1.5 text-sm">
                    {p.contradictions.map((c, i) => (
                      <li key={i} className="flex justify-between gap-3">
                        <Link to={`/tracks/${c.track.asset_id}`} className="truncate hover:text-violet-soft">{c.track.title}</Link>
                        <span className="shrink-0 font-mono text-xs text-muted">{c.track.value_label}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              )}
            </div>
          </div>

          {p.associations.length > 0 && (
            <Panel eyebrow={<span className="flex items-center gap-2">Edistynyt <CategoryBadge cat="statistical" /></span>} title="Kaikki raportoidut yhteydet">
              <details>
                <summary className="cursor-pointer text-sm text-violet-soft select-none">Näytä {p.associations.length} yhteyttä ({p.associations_tested} testattiin)</summary>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-faint">
                        <th className="pb-2 font-normal">Kokemus</th>
                        <th className="pb-2 font-normal">Piirre</th>
                        <th className="pb-2 font-normal">ρ</th>
                        <th className="pb-2 font-normal">95 % CI</th>
                        <th className="pb-2 font-normal">n</th>
                        <th className="pb-2 font-normal">p (perm.)</th>
                        <th className="pb-2 font-normal">q (FDR)</th>
                        <th className="pb-2 font-normal">Taso</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono tabular">
                      {p.associations.map((a, i) => (
                        <tr key={i} className="border-t border-line/60">
                          <td className="py-1.5 pr-2 font-sans">{a.dimension_label}</td>
                          <td className="py-1.5 pr-2 font-sans">{a.feature_label}</td>
                          <td className={`py-1.5 pr-2 ${a.rho > 0 ? "text-violet-soft" : "text-cyan"}`}>{a.rho.toFixed(2)}</td>
                          <td className="py-1.5 pr-2 text-muted">{a.ci_low !== null ? `${a.ci_low.toFixed(2)}…${a.ci_high?.toFixed(2)}` : "–"}</td>
                          <td className="py-1.5 pr-2">{a.n}</td>
                          <td className="py-1.5 pr-2">{a.p_permutation.toFixed(3)}</td>
                          <td className="py-1.5 pr-2">{a.q_fdr.toFixed(3)}</td>
                          <td className="py-1.5 font-sans">
                            <EvidenceBadge level={a.evidence_level} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-3 text-2xs text-faint">
                    Spearmanin järjestyskorrelaatio, kaksisuuntainen permutaatiotesti (1000 permutaatiota), Benjamini–Hochberg-korjaus kaikkien testien yli ja bootstrap-luottamusväli. Monta testiä
                    pienellä aineistolla tuottaa väistämättä sattumayhteyksiä – siksi näytön tasot.
                  </p>
                </div>
              </details>
            </Panel>
          )}

          {history.data && history.data.length > 1 && (
            <Panel eyebrow="Kehitys" title="Profiilin versiohistoria">
              <ol className="flex flex-col gap-2 text-sm">
                {history.data.slice(0, 8).map((h) => (
                  <li key={h.version} className="flex flex-wrap items-center gap-3">
                    <span className="w-10 font-mono text-violet-soft">v{h.version}</span>
                    <span className="w-36 text-xs text-muted">{fmtDate(h.created_at)}</span>
                    <span className="text-xs text-muted">
                      {h.tracks_rated} arvioitua · {h.insights} havaintoa
                    </span>
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}
