import { FusionIcon } from "@/design-system/brand";
import { ModulePreview } from "@/components/ModulePreview";

export default function FusionStudioPage() {
  return (
    <ModulePreview
      eyebrow="Fusion Studio · Where sound becomes vision"
      icon={<FusionIcon size={14} />}
      title="Fusion Studio"
      tagline="Audiovisuaalinen luova työtila: millainen visuaalinen kokemus voisi vahvistaa juuri sinun kokemustasi tästä kappaleesta?"
      phase="vaihe 5"
      description="Fusion Studio yhdistää SonicDNA:n ja VisualDNA:n. Se ehdottaa musiikin rakenteeseen ajastetun visuaalisen aikajanan ja kohtauskohtaiset kehotteet Suno Visuals -työnkulkua varten. Kyse on hypoteesien luomisesta – ei psykologisesta varmuudesta. Sovellus ei renderöi musiikkivideota ennen kuin tarvittava integraatio on olemassa."
      planned={[
        "Musiikin osiin, energiamuutoksiin, nousuihin ja omiin merkintöihisi ajastettu visuaalinen aikajana",
        "Storyboard: konsepti, kohtaukset, kestot, jatkuvuussäännöt, kamera, valo ja väri",
        "Suno Visuals -yhteensopivat 5–15 s klippikehotteet (16:9 ja 9:16), ominaisuudet varmennetaan ennen toteutusta",
        "Yksittäisten kohtausten muokkaus ilman koko suunnitelman uudelleenluontia",
        "Audiovisuaalinen palaute: musiikki yksin, kuva yksin ja yhdistelmä erikseen",
      ]}
      foundations={[
        "SonicDNA-rakenneanalyysi: osat, energiakaari, huippuhetket ja nousut",
        "Hetkimerkinnät tunnehuipuille ja kehollisille reaktioille",
        "Prompt-spesifikaatio, joka on erotettu palveluntarjoajan formaatista",
      ]}
    />
  );
}
