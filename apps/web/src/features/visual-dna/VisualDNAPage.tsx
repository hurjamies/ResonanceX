import { VisualIcon } from "@/design-system/brand";
import { ModulePreview } from "@/components/ModulePreview";

export default function VisualDNAPage() {
  return (
    <ModulePreview
      eyebrow="VisualDNA · Discover what your eyes feel"
      icon={<VisualIcon size={14} />}
      title="VisualDNA"
      tagline="Henkilökohtainen visuaalinen älykkyys: mitkä kuvan ja liikkeen ominaisuudet koskettavat sinua."
      phase="vaihe 4"
      description="VisualDNA rakennetaan samoille periaatteille kuin SonicDNA: mitatut kuvapiirteet erotetaan mallien tulkinnoista ja omista kokemuksistasi. Arkkityyppiset tulkinnat (esim. varjo, kynnys, muutos) tarjotaan vain valinnaisina tulkintatyökaluina, joita voit hyväksyä tai hylätä – ei koskaan väitteinä tiedostamattomastasi."
      planned={[
        "Kuvien ja videoiden tuonti (JPG, PNG, WebP, FFmpeg-videot), kokoelmat ja suosikit",
        "Mitattavat piirteet: väripaletti, kirkkaus, kontrasti, saturaatio, värilämpötila, reunatiheys, sommittelu",
        "Videot: kohtausvaihdokset, liikkeen intensiteetti, otosten pituus, visuaalinen rytmi",
        "Visuaaliset kokemusarviot (vetovoima, kauneus, mystisyys, nostalgia, ihmetys…) ja vapaa pohdinta",
        "Henkilökohtainen VisualDNA-profiili näyttöineen ja epävarmuuksineen",
        "Visual Prompt Studio kuva- ja videogeneraattoreille",
      ]}
      foundations={[
        "Yhteinen Resonance Core -tilastomoottori (näytön tasot, permutaatiotestit, vastaesimerkit)",
        "MediaAsset-tietomalli tukee jo media-tyyppiä (audio/image/video)",
        "Prompt-spesifikaation ja palveluntarjoajakääntäjän erottelu",
        "Paikallinen, yksityisyyttä suojaava tallennus",
      ]}
    />
  );
}
