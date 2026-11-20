import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button, ErrorNote, Spinner } from "@/components/ui";
import { api, qk } from "@/services/api";

export function ForYouCard() {
  const suggestion = useQuery({
    queryKey: qk.musicSuggestion,
    queryFn: api.musicSuggestion,
    refetchInterval: (q) => q.state.data?.pending_count ? 2000 : false,
  });
  const qc = useQueryClient();
  const navigate = useNavigate();
  const generate = useMutation({
    mutationFn: api.suggestionPrompt,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: qk.prompts });
      qc.invalidateQueries({ queryKey: qk.overview });
      navigate(`/prompt-studio?batch=${result.batch_id}&quick=1`);
    },
  });
  const s = suggestion.data;

  return (
    <section className="rounded-2xl border border-violet/25 bg-violet/5 p-5 sm:p-7" aria-label="Sinulle">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0 max-w-2xl flex-1">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-violet-soft"><Sparkles className="size-4" /> Sinulle</div>
          {suggestion.isLoading ? <Spinner label="Etsitään sinun soundiasi…" /> : null}
          {s ? (
            <>
              <h2 className="text-xl font-semibold sm:text-2xl">{s.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted">{s.description}</p>
              {s.genres.length > 0 ? <div className="mt-4 flex flex-wrap gap-2">{s.genres.map((g) => <span key={g} className="rounded-full bg-surface px-3 py-1 text-sm">{g}</span>)}</div> : null}
              {s.sound_summary.length > 0 ? <p className="mt-3 text-sm text-ink">{s.sound_summary.join(" · ")}</p> : null}
              <p className="mt-4 text-xs text-muted">{s.tracks_considered} analysoitua kappaletta · {s.ratings_count} mieltymysarviota · kaikki lokerot mukana</p>
            </>
          ) : null}
          <ErrorNote error={suggestion.error} />
          {suggestion.error ? <Button size="sm" className="mt-3" onClick={() => suggestion.refetch()}>Yritä uudelleen</Button> : null}
        </div>
        {s ? <div className="flex flex-col items-start gap-2 sm:max-w-64 sm:pt-7">
          {s.ready ? (
            <Button variant="primary" loading={generate.isPending} onClick={() => generate.mutate()}>Luo minulle Suno-kehote <ArrowRight className="size-4" /></Button>
          ) : (
            <Link to={s.rate_asset_id ? `/tracks/${s.rate_asset_id}` : "/library"} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-soft">
              {s.rate_asset_id ? "Arvioi kappale" : "Lisää ensimmäinen kappale"} <ArrowRight className="size-4" />
            </Link>
          )}
          <p className="text-xs leading-relaxed text-muted">{s.ready ? "Saat valmiin kehotteen kopioitavaksi Sunoon." : "Mieltymysarvio kertoo, mistä pidät."}</p>
        </div> : null}
      </div>
      <ErrorNote error={generate.error} />
      {s?.ready ? <details className="mt-5 border-t border-line pt-4 text-sm">
        <summary className="cursor-pointer text-muted hover:text-ink">Miksi tämä voisi sopia minulle?</summary>
        <ul className="mt-3 flex list-inside list-disc flex-col gap-2 text-muted">{s.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">{s.sources.map((t) => <Link key={t.id} to={`/tracks/${t.id}`} className="text-violet-soft hover:underline">{t.title} · {t.preference}/10</Link>)}</div>
        <p className="mt-3 text-xs text-muted">{s.note}</p>
      </details> : null}
    </section>
  );
}
