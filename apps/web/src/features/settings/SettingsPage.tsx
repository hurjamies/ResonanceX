import { useQuery } from "@tanstack/react-query";
import { Download, HardDrive, Lock, Plug, Settings } from "lucide-react";
import { Button, PageHeader, Panel, Spinner } from "@/components/ui";
import { api, qk } from "@/services/api";
import { fmtBytes } from "@/services/format";

const STATUS_CLS: Record<string, string> = {
  available: "border-ok/40 text-ok",
  verified: "border-ok/40 text-ok",
  configured: "border-cyan/40 text-cyan",
  external: "border-gold/40 text-gold",
  not_configured: "border-line-strong text-faint",
};
const STATUS_LABEL: Record<string, string> = {
  available: "Käytössä",
  verified: "Varmennettu",
  configured: "Määritetty",
  external: "Claude Code",
  not_configured: "Ei määritetty",
};

export default function SettingsPage() {
  const s = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const providers = useQuery({ queryKey: qk.providers, queryFn: api.providers });
  return (
    <div>
      <PageHeader eyebrow="Asetukset" icon={<Settings className="size-3.5" />} title="Asetukset" description="Paikallinen tallennus, palveluntarjoajat, yksityisyys ja tietojen vienti." />
      {s.isLoading || !s.data ? (
        <Spinner />
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          <Panel eyebrow={<span className="flex items-center gap-2"><HardDrive className="size-3.5" /> Paikallinen tallennus</span>} title="Tiedot pysyvät koneellasi">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted">Datahakemisto</dt>
              <dd className="truncate font-mono text-xs">{s.data.data_dir}</dd>
              <dt className="text-muted">Tietokanta</dt>
              <dd className="truncate font-mono text-xs">{s.data.database}</dd>
              <dt className="text-muted">Alkuperäiset tiedostot</dt>
              <dd className="font-mono text-xs">{fmtBytes(s.data.uploads_bytes)}</dd>
              <dt className="text-muted">Analyysidata</dt>
              <dd className="font-mono text-xs">{fmtBytes(s.data.analysis_bytes)}</dd>
              <dt className="text-muted">Latausraja</dt>
              <dd className="font-mono text-xs">{s.data.max_upload_mb} Mt · {Math.round(s.data.max_duration_seconds / 60)} min</dd>
              <dt className="text-muted">Analyysiversio</dt>
              <dd className="font-mono text-xs">{s.data.analysis_version} · {s.data.core_version}</dd>
              <dt className="text-muted">FFmpeg</dt>
              <dd className={s.data.ffmpeg ? "text-ok" : "text-danger"}>{s.data.ffmpeg ? "käytettävissä" : "puuttuu – asenna FFmpeg"}</dd>
              <dt className="text-muted">Palvelin</dt>
              <dd className="font-mono text-xs">{s.data.bind_host} (vain paikallinen)</dd>
            </dl>
          </Panel>

          <Panel eyebrow={<span className="flex items-center gap-2"><Lock className="size-3.5" /> Yksityisyys</span>} title="Mitä sovellus lähettää ulos?">
            <p className="text-sm text-ink">Ei mitään ilman nimenomaista toimintaasi.</p>
            <ul className="mt-2 flex flex-col gap-1.5 text-sm text-muted">
              <li>• Äänitiedostot, analyysit, arviot ja kirjoitetut pohdinnat tallennetaan vain paikalliseen SQLite-tietokantaan ja datahakemistoon.</li>
              <li>• Suno-kehotteet siirtyvät Sunoon vain, kun itse kopioit ne tai Claude Code lähettää ne hyväksynnälläsi.</li>
              <li>• ElevenLabsille lähtee vain musiikillinen kuvausteksti – ja vain kun vahvistat pyynnön. Ennen sitä näet täsmällisen sisällön.</li>
              <li>• Fontit ja kirjastot ladataan paikallisesti – ei ulkoisia CDN- tai analytiikkapyyntöjä.</li>
              <li>• Kielimalli: {s.data.llm.status_fi}</li>
            </ul>
          </Panel>

          <Panel eyebrow={<span className="flex items-center gap-2"><Plug className="size-3.5" /> Palveluntarjoajat</span>} title="Generointipalvelut" className="xl:col-span-2">
            <ul className="grid gap-3 lg:grid-cols-3">
              {(providers.data ?? []).map((p) => (
                <li key={p.id} className="flex flex-col rounded-lg border border-line p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display font-medium">{p.name}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-2xs ${STATUS_CLS[p.status] ?? "border-line text-muted"}`}>{STATUS_LABEL[p.status] ?? p.status}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted">{p.status_fi}</p>
                  {p.last_success_at && <p className="mt-1 text-2xs text-ok">Viimeisin onnistunut: {new Date(p.last_success_at).toLocaleString("fi-FI")}</p>}
                  <ol className="mt-3 flex list-decimal flex-col gap-1 pl-4 text-xs text-muted">
                    {p.setup_fi.map((x) => (
                      <li key={x} className="break-words">{x}</li>
                    ))}
                  </ol>
                  {p.cost && <p className="mt-3 text-2xs text-gold">{p.cost.basis_fi} Pyyntökohtainen raja {p.cost.max_per_request_usd.toFixed(2)} $.</p>}
                  <p className="mt-3 text-2xs text-faint">{p.notes_fi}</p>
                  <div className="mt-auto flex flex-wrap gap-x-3 pt-3">
                    {p.docs.map((d) => (
                      <a key={d} href={d} target="_blank" rel="noreferrer noopener" className="truncate text-2xs text-violet-soft hover:underline">
                        {new URL(d).hostname}
                        {new URL(d).pathname.slice(0, 28)}
                      </a>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-2xs text-faint">Sovellus ei koskaan käynnistä maksullista generointia automaattisesti: jokainen pyyntö näytetään ensin täsmällisenä, kustannusarvio on hyväksyttävä erikseen, eikä keskeytyneitä pyyntöjä lähetetä uudelleen. API-avaimet luetaan vain palvelimen ympäristöstä.</p>
          </Panel>

          <Panel eyebrow={<span className="flex items-center gap-2"><Download className="size-3.5" /> Vienti</span>} title="Omista tietosi" className="xl:col-span-2">
            <div className="flex flex-wrap gap-2">
              <a href="/api/export/all.json"><Button>Kaikki tiedot (JSON)</Button></a>
              <a href="/api/export/profile.json"><Button>SonicDNA-profiili (JSON)</Button></a>
              <a href="/api/export/ratings.csv"><Button>Arviot + piirteet (CSV)</Button></a>
            </div>
            <p className="mt-3 text-xs text-muted">Kokonaisvienti sisältää kappaleiden metatiedot, analyysiyhteenvedot, arviot, merkinnät, vertailut, kehotteet, kokeet ja profiilin. Alkuperäiset äänitiedostot löytyvät datahakemistosta.</p>
          </Panel>
        </div>
      )}
    </div>
  );
}
