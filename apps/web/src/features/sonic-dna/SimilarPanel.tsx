import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CategoryBadge, Panel, Spinner } from "@/components/ui";
import { api, qk } from "@/services/api";

/** Cross-genre discovery: nearest neighbours in standardised feature space. */
export function SimilarPanel({ assetId }: { assetId: number }) {
  const q = useQuery({ queryKey: qk.similar(assetId), queryFn: () => api.similar(assetId) });
  return (
    <Panel eyebrow={<span className="flex items-center gap-2">Rakenteellinen samankaltaisuus <CategoryBadge cat="statistical" /></span>} title="Samankaltaiset kappaleet kirjastossasi">
      {q.isLoading ? (
        <Spinner />
      ) : !q.data?.length ? (
        <p className="text-sm text-muted">Vertailu vaatii vähintään kolme analysoitua kappaletta.</p>
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {q.data.map((s) => (
              <li key={s.asset_id} className="rounded-lg border border-line px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <Link to={`/tracks/${s.asset_id}`} className="truncate text-sm text-ink hover:text-violet-soft">
                    {s.title} {s.artist && <span className="text-muted">– {s.artist}</span>}
                  </Link>
                  <span className="shrink-0 font-mono text-2xs text-faint">etäisyys {s.distance.toFixed(2)}</span>
                </div>
                {s.shared_features.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {s.shared_features.map((f) => (
                      <span key={f.feature} className="rounded-full bg-violet/10 px-2 py-0.5 text-2xs text-violet-soft">
                        {f.phrase}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-2xs text-faint">
            Etäisyys lasketaan kirjastosi sisällä robustisti standardoiduista SonicDNA-piirteistä (rytmi, spektri, harmonia, dynamiikka, rakenne) – ei genrestä. Korostetut piirteet ovat yhteisiä ja
            kirjastossasi poikkeuksellisia.
          </p>
        </>
      )}
    </Panel>
  );
}
