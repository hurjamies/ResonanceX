import { Link } from "react-router-dom";
import { AtlasIcon } from "@/design-system/brand";
import { ModulePreview } from "@/components/ModulePreview";

export default function AtlasPage() {
  return (
    <>
      <ModulePreview
        eyebrow="Resonance Atlas · Explore your inner universe"
        icon={<AtlasIcon size={14} />}
        title="Resonance Atlas"
        tagline="Kokemustesi, piirteiden ja kokeiden välisten suhteiden tutkiva kartta."
        phase="vaihe 6"
        description="Atlas näyttää kappaleet, kuvat, kokemukset ja kokeet kartalla, jonka samankaltaisuusmenetelmä on aina ilmoitettu ja toistettavissa – rytminen, harmoninen, visuaalinen, koettu tai monimodaalinen. Äänipiirteisiin perustuvaa karttaa ei esitetä tunnekarttana. Harvalla aineistolla Atlas ohjaa vertailuihin merkityksettömien klustereiden sijaan."
        planned={[
          "Vaihdettavat suhdetyypit: rytminen, harmoninen, visuaalinen paletti, koettu tunne, resonanssi, monimodaalinen",
          "Kohteen avaaminen: media, analyysi, arviot, perustelevat samankaltaisuudet, kehotteet ja kokeet",
          "Mieltymysten kehitys ajassa profiiliversioiden kautta",
          "Odottamattomien yhteyksien ja kokeiden suositukset",
        ]}
        foundations={[
          "Resonance Field (SonicDNA-näkymässä): PCA- tai piirreakselikartta omista kappaleistasi",
          "Rakenteellisen samankaltaisuuden haku jokaisella kappalesivulla",
          "Versioidut profiilit, joista kehitystä voidaan seurata",
        ]}
      />
      <p className="mt-5 text-sm text-muted">
        Ensimmäinen versio karttanäkymästä on jo käytössä: <Link to="/sonic-dna" className="text-violet-soft hover:underline">SonicDNA → Resonance Field</Link>.
      </p>
    </>
  );
}
