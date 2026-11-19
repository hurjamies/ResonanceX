import clsx from "clsx";
import { Info } from "lucide-react";
import type { ReactNode } from "react";
import { CategoryBadge, type Category, Panel, Tabs } from "@/components/ui";
import { BAND_COLORS, BAND_FI, fmtNum, fmtTime } from "@/services/format";
import { usePlayer } from "@/stores/player";
import type { Analysis, TimeSeries } from "@/types/api";
import { useState } from "react";
import { ROLE_FI, valueAt } from "./timeline";

const ARC_FI: Record<string, string> = {
  plateau: "Tasainen energia",
  gradual_build: "Asteittainen nousu",
  sudden_contrasts: "Äkilliset kontrastit",
  early_peak: "Varhainen huippu",
  waves: "Aaltoileva energia",
};

function Row({ label, value, cat, hint }: { label: string; value: ReactNode; cat: Category; hint?: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line/70 py-2 last:border-0">
      <div className="max-w-[55%] shrink-0">
        <div className="flex items-center gap-1.5 text-sm text-muted">
          {label}
          {hint && (
            <span title={hint} className="text-faint">
              <Info className="size-3" />
            </span>
          )}
        </div>
      </div>
      <div className="flex min-w-0 flex-col items-end gap-1">
        <div className="text-right font-mono text-sm break-words text-ink tabular">{value}</div>
        <CategoryBadge cat={cat} />
      </div>
    </div>
  );
}

function Meter({ value, max = 1 }: { value: number | null; max?: number }) {
  if (value === null) return <span className="text-faint">–</span>;
  return (
    <span className="inline-flex items-center gap-2">
      <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-surface">
        <span className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-violet to-cyan" style={{ width: `${Math.max(2, Math.min(100, (value / max) * 100))}%` }} />
      </span>
      {fmtNum(value, 2)}
    </span>
  );
}

export function AnalysisPanels({ analysis }: { analysis: Analysis }) {
  const [tab, setTab] = useState<"rhythm" | "spectral" | "tonality" | "dynamics" | "structure">("rhythm");
  const s = analysis.summary;
  const r = s.rhythm;
  const sp = s.spectral;
  const t = s.tonality;
  const d = s.dynamics;
  const st = s.structure;
  const seek = usePlayer((x) => x.seek);
  return (
    <Panel
      eyebrow="SonicDNA-analyysi"
      title="Mitatut ja arvioidut piirteet"
      actions={<span className="font-mono text-2xs text-faint">{analysis.algorithm_version} · {analysis.analysis_seconds.toFixed(1)} s</span>}
    >
      <Tabs
        className="mb-4"
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "rhythm", label: "Rytmi" },
          { key: "spectral", label: "Spektri" },
          { key: "tonality", label: "Harmonia" },
          { key: "dynamics", label: "Dynamiikka" },
          { key: "structure", label: "Rakenne" },
        ]}
      />
      {tab === "rhythm" && (
        <div>
          <Row
            label="Tempo"
            cat="estimated"
            value={
              <span>
                {fmtNum(r.tempo_bpm, 1)} BPM <span className="text-faint">· luottamus {fmtNum(r.tempo_confidence, 2)}</span>
              </span>
            }
          />
          {r.tempo_ambiguity && (
            <div className="my-2 rounded-lg border border-gold/30 bg-gold/5 px-3 py-2 text-xs text-gold">
              Metrinen monitulkintaisuus: myös {r.tempo_ambiguity.alternative_bpm} BPM ({AMB_FI[r.tempo_ambiguity.kind] ?? r.tempo_ambiguity.kind}) on uskottava tulkinta. Yksittäistä BPM-arvoa ei pidä pitää varmana.
            </div>
          )}
          <Row label="Tempoehdokkaat" cat="estimated" value={r.tempo_candidates.slice(0, 3).map((c) => `${c.bpm.toFixed(0)}`).join(" · ")} hint="Iskuvoimakkuuskäyrän autokorrelaation vahvimmat jaksot" />
          <Row label="Tempon vaihtelu" cat="estimated" value={`± ${fmtNum(r.tempo_variation_bpm, 1)} BPM`} />
          <Row label="Pulssin selkeys" cat="estimated" value={<Meter value={r.pulse_clarity} />} />
          <Row label="Rytminen säännöllisyys" cat="estimated" value={<Meter value={r.rhythmic_regularity} />} hint="Iskuvälien vaihtelusta, kehysten kvantisointi huomioiden" />
          <Row label="Iskutiheys" cat="measured" value={`${fmtNum(r.onset_density, 2)} /s`} />
          <Row label="Iskun voimakkuus" cat="estimated" value={fmtNum(r.beat_strength, 2)} hint="Iskukohtien keskimääräinen voimakkuus suhteessa koko kappaleeseen" />
          <Row label="Synkopointi" cat="estimated" value={<Meter value={r.syncopation} />} hint="Karkea arvio: välipulssien voimakkuus suhteessa iskuihin. Heikko luotettavuus." />
          <Row label="Swing-suhde" cat="estimated" value={r.swing_ratio ? `${fmtNum(r.swing_ratio, 2)} (luottamus ${fmtNum(r.swing_confidence, 2)})` : "ei havaittavissa"} hint="1.0 = suora, ~2.0 = kolmimuunteinen swing" />
          <Row label="Rytminen toisto" cat="estimated" value={<Meter value={r.rhythmic_repetition} />} hint="Peräkkäisten 4 iskun kuvioiden samankaltaisuus (olettaa 4/4-tahdin)" />
        </div>
      )}
      {tab === "spectral" && (
        <div>
          <div className="mb-4">
            <div className="eyebrow mb-2">Energian jakauma taajuuskaistoittain</div>
            <div className="flex h-3 overflow-hidden rounded-full">
              {Object.entries(sp.band_energy_ratio).map(([k, v]) => (
                <div key={k} style={{ width: `${(v ?? 0) * 100}%`, background: BAND_COLORS[k] }} title={`${BAND_FI[k]} ${((v ?? 0) * 100).toFixed(1)} %`} />
              ))}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-5">
              {Object.entries(sp.band_energy_ratio).map(([k, v]) => (
                <div key={k} className="flex items-center gap-1.5">
                  <span className="size-2 rounded-full" style={{ background: BAND_COLORS[k] }} />
                  <span className="text-muted">{BAND_FI[k]}</span>
                  <span className="ml-auto font-mono tabular">{((v ?? 0) * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-2xs text-faint">
              Äänitteen fyysinen spektri. Kehoon välittyvä värähtely riippuu toistolaitteesta, äänenvoimakkuudesta, tilasta ja fysiologiasta – sitä ei mitata.
            </p>
          </div>
          <Row label="Spektrin sentroidi (kirkkaus)" cat="measured" value={`${fmtNum(sp.centroid_mean_hz, 0)} Hz`} />
          <Row label="Rolloff (85 %)" cat="measured" value={`${fmtNum(sp.rolloff_mean_hz, 0)} Hz`} />
          <Row label="Kaistanleveys" cat="measured" value={`${fmtNum(sp.bandwidth_mean_hz, 0)} Hz`} />
          <Row label="Spektrin tasaisuus" cat="measured" value={fmtNum(sp.flatness_mean, 4)} hint="0 = sävyisä, 1 = kohinamainen" />
          <Row label="Bassopulssin taajuus" cat="measured" value={sp.bass_modulation.rate_hz ? `${fmtNum(sp.bass_modulation.rate_hz, 2)} Hz` : "–"} hint="Bassoenergian verhokäyrän vallitseva modulaatiotaajuus" />
          <Row label="Bassopulssi / isku" cat="estimated" value={sp.bass_modulation.beat_relation ? `${fmtNum(sp.bass_modulation.beat_relation, 2)} × tempo` : "–"} hint="1 = bassopulssi jokaisella iskulla, 0.5 = joka toisella, 2 = kahdeksasosin" />
          <Row label="Bassovaihtelun syvyys" cat="measured" value={fmtNum(sp.bass_modulation.depth, 2)} />
        </div>
      )}
      {tab === "tonality" && (
        <div>
          <Row label="Sävelkeskus ja moodi" cat="estimated" value={<span>{t.key_label} <span className="text-faint">· luottamus {fmtNum(t.key_confidence, 2)}</span></span>} />
          <div className="my-2 text-xs text-muted">
            Ehdokkaat:{" "}
            {t.key_candidates.map((k) => `${k.key} ${k.mode === "major" ? "duuri" : "molli"} (${k.correlation.toFixed(2)})`).join(" · ")}
            <div className="mt-1 text-2xs text-faint">Rinnakkaisduuri ja -molli sekoittuvat usein; matala luottamus tarkoittaa monitulkintaista sävelkeskusta.</div>
          </div>
          <div className="my-4">
            <div className="eyebrow mb-2">Sävelluokkajakauma</div>
            <div className="flex h-20 items-end gap-1">
              {t.pitch_class_distribution.map((v, i) => {
                const max = Math.max(...t.pitch_class_distribution);
                return (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1">
                    <div className="w-full rounded-t bg-gradient-to-t from-violet/60 to-lavender" style={{ height: `${(v / max) * 60}px` }} />
                    <span className="font-mono text-[9px] text-faint">{PCS[i]}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <Row label="Harmoninen vakaus" cat="estimated" value={<Meter value={t.harmonic_stability} />} />
          <Row label="Sointuvaihdoksia" cat="estimated" value={`${fmtNum(t.chord_change_rate_per_min, 1)} /min`} />
          <Row label="Eri sointuja" cat="estimated" value={t.chord_vocabulary_size} />
          <Row label="Harmoninen toisto" cat="estimated" value={<Meter value={t.harmonic_repetition} />} hint="Toistuvien 4 soinnun kulkujen osuus" />
          <Row label="Tonaalinen jännite (proksi)" cat="estimated" value={<Meter value={t.tonal_tension_mean} />} hint="1 − paikallisen kromaprofiilin korrelaatio sävellajiprofiiliin" />
          <p className="mt-3 text-2xs text-faint">Soinnut: {t.chord_method}.</p>
        </div>
      )}
      {tab === "dynamics" && (
        <div>
          <Row label="Integroitu äänekkyys" cat="measured" value={`${fmtNum(d.integrated_loudness_lufs, 1)} LUFS`} hint={d.loudness_note} />
          <Row label="Äänekkyyden vaihteluväli" cat="measured" value={`${fmtNum(d.loudness_range_lu, 1)} LU`} hint="EBU R128 LRA -tyyppinen (10.–95. persentiili)" />
          <Row label="Huippukerroin" cat="measured" value={`${fmtNum(d.crest_factor_db, 1)} dB`} />
          <Row label="Huipputaso" cat="measured" value={`${fmtNum(d.peak_dbfs, 1)} dBFS`} />
          <Row label="Harmoninen/perkussiivinen" cat="estimated" value={`${fmtNum(d.harmonic_percussive_ratio, 2)} (perk. ${((d.percussive_fraction ?? 0) * 100).toFixed(0)} %)`} hint="HPSS-erottelun energiasuhde" />
          <Row label="Stereoleveys" cat="measured" value={d.stereo_width === null ? "mono" : fmtNum(d.stereo_width, 3)} hint="Sivu/keski-signaalin RMS-suhde" />
          <Row label="Kanavakorrelaatio" cat="measured" value={fmtNum(d.stereo_correlation, 3)} />
          <Row label="Tekstuurin tiheys" cat="estimated" value={<Meter value={d.texture_density} />} hint="Mel-kaistojen osuus, jotka ovat 30 dB:n sisällä kehyksen voimakkaimmasta" />
          <Row label="Hiljaisuuden osuus" cat="measured" value={`${((d.silence_fraction ?? 0) * 100).toFixed(1)} %`} />
        </div>
      )}
      {tab === "structure" && (
        <div>
          <Row label="Energiakaari" cat="estimated" value={ARC_FI[st.energy_arc.type] ?? st.energy_arc.type} />
          <Row label="Huipun sijainti" cat="estimated" value={`${((st.energy_arc.peak_position ?? 0) * 100).toFixed(0)} % kestosta`} />
          <Row label="Nousun asteittaisuus" cat="estimated" value={fmtNum(st.energy_arc.build_gradualness, 2)} hint="Spearman-korrelaatio ajan ja energian välillä ennen huippua" />
          <Row label="Pisin crescendo" cat="estimated" value={`${fmtNum(st.energy_arc.crescendo_seconds, 0)} s`} />
          <Row label="Äkilliset energiahypyt" cat="estimated" value={st.energy_arc.sudden_changes} />
          <Row label="Rakenteellinen toisto" cat="estimated" value={<Meter value={st.structural_repetition} />} />
          <div className="mt-4">
            <div className="eyebrow mb-2">Ehdotetut osat (likimääräiset)</div>
            <ul className="flex flex-col gap-1">
              {analysis.segments.map((sg) => (
                <li key={sg.index}>
                  <button onClick={() => seek(sg.start)} className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface/50">
                    <span className="w-6 font-display font-semibold text-violet-soft">{sg.letter}</span>
                    <span className="w-24 font-mono text-xs text-cyan tabular">{fmtTime(sg.start)}–{fmtTime(sg.end)}</span>
                    <span className="flex-1">{ROLE_FI[sg.role] ?? sg.role}</span>
                    <span className={clsx("font-mono text-xs tabular", sg.relative_energy_db >= 0 ? "text-gold" : "text-muted")}>
                      {sg.relative_energy_db >= 0 ? "+" : ""}
                      {sg.relative_energy_db.toFixed(1)} dB
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-2xs text-faint">{st.method}</p>
          </div>
        </div>
      )}
    </Panel>
  );
}

const PCS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const AMB_FI: Record<string, string> = { half: "puolinopeus", double: "tuplanopeus", three_halves: "3:2", two_thirds: "2:3" };

/** What happens musically at the current playback position? */
export function MomentInspector({ analysis, ts }: { analysis: Analysis; ts: TimeSeries }) {
  const t = usePlayer((s) => s.currentTime);
  const pct = (series: (number | null)[], v: number | null) => {
    if (v === null) return null;
    const vals = series.filter((x): x is number => x !== null);
    return vals.filter((x) => x < v).length / Math.max(1, vals.length);
  };
  const energy = valueAt(ts.energy_env_db, ts.dt, t);
  const rms = valueAt(ts.rms_db, ts.dt, t);
  const cent = valueAt(ts.centroid_hz, ts.dt, t);
  const tempo = valueAt(ts.local_tempo, ts.local_tempo_dt, t);
  const seg = analysis.segments.find((s) => s.start <= t && s.end > t);
  const chord = analysis.summary.tonality.chords.find((c) => c.start <= t && c.end > t);
  const bassDb = (() => {
    const a = valueAt(ts.bands.sub_bass, ts.dt, t);
    const b = valueAt(ts.bands.bass, ts.dt, t);
    if (a === null || b === null) return null;
    return 10 * Math.log10(10 ** (a / 10) + 10 ** (b / 10));
  })();
  const bassSeries = ts.bands.bass;
  const rise = (() => {
    const i = Math.floor(t / ts.dt);
    const j = i - Math.round(8 / ts.dt);
    const a = ts.energy_env_db[i];
    const b = j >= 0 ? ts.energy_env_db[j] : null;
    return a !== null && a !== undefined && b !== null && b !== undefined ? a - b : null;
  })();
  const items: { label: string; value: string; p?: number | null }[] = [
    { label: "Osa", value: seg ? `${seg.letter} · ${ROLE_FI[seg.role] ?? seg.role}` : "–" },
    { label: "Sointu (arvio)", value: chord && chord.label !== "N" ? chord.label : "–" },
    { label: "Energia (5 s)", value: energy === null ? "–" : `${energy.toFixed(1)} dB`, p: pct(ts.energy_env_db, energy) },
    { label: "Energian muutos 8 s", value: rise === null ? "–" : `${rise > 0 ? "+" : ""}${rise.toFixed(1)} dB` },
    { label: "Hetkellinen taso", value: rms === null ? "–" : `${rms.toFixed(1)} dBFS`, p: pct(ts.rms_db, rms) },
    { label: "Basso", value: bassDb === null ? "–" : `${bassDb.toFixed(1)} dB`, p: pct(bassSeries, valueAt(bassSeries, ts.dt, t)) },
    { label: "Kirkkaus", value: cent === null ? "–" : `${Math.round(cent)} Hz`, p: pct(ts.centroid_hz, cent) },
    { label: "Paikallinen tempo", value: tempo === null ? "–" : `${tempo.toFixed(1)} BPM` },
  ];
  return (
    <Panel eyebrow={<span className="font-mono tabular">Hetki {fmtTime(t, true)}</span>} title="Mitä musiikissa tapahtuu nyt?">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        {items.map((it) => (
          <div key={it.label}>
            <dt className="text-2xs text-faint">{it.label}</dt>
            <dd className="font-mono text-sm text-ink tabular">{it.value}</dd>
            {it.p !== undefined && it.p !== null && (
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface" title={`${Math.round(it.p * 100)}. persentiili tässä kappaleessa`}>
                <div className="h-full bg-cyan/70" style={{ width: `${it.p * 100}%` }} />
              </div>
            )}
          </div>
        ))}
      </dl>
      <p className="mt-3 text-2xs text-faint">Palkit: arvon sijainti tämän kappaleen omassa jakaumassa. Klikkaa aikajanaa tutkiaksesi muita hetkiä.</p>
    </Panel>
  );
}
