import clsx from "clsx";
import { FlaskConical, Library, LayoutDashboard, Menu, Pause, Play, Settings, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { AtlasIcon, FusionIcon, PromptIcon, ResonanceMark, SonicIcon, VisualIcon, Wordmark } from "@/design-system/brand";
import { fmtTime } from "@/services/format";
import { usePlayer } from "@/stores/player";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  preview?: boolean;
}

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Tutki",
    items: [
      { to: "/", label: "Yleiskatsaus", icon: <LayoutDashboard className="size-[18px]" /> },
      { to: "/library", label: "Kirjasto", icon: <Library className="size-[18px]" /> },
      { to: "/sonic-dna", label: "SonicDNA", icon: <SonicIcon size={18} /> },
      { to: "/visual-dna", label: "VisualDNA", icon: <VisualIcon size={18} />, preview: true },
    ],
  },
  {
    group: "Luo",
    items: [
      { to: "/prompt-studio", label: "Prompt Studio", icon: <PromptIcon size={18} /> },
      { to: "/experiments", label: "Kokeet", icon: <FlaskConical className="size-[18px]" /> },
      { to: "/fusion-studio", label: "Fusion Studio", icon: <FusionIcon size={18} />, preview: true },
      { to: "/atlas", label: "Resonance Atlas", icon: <AtlasIcon size={18} />, preview: true },
    ],
  },
  { group: "", items: [{ to: "/settings", label: "Asetukset", icon: <Settings className="size-[18px]" /> }] },
];

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Päävalikko" className="flex flex-col gap-5">
      {NAV.map((g, gi) => (
        <div key={gi}>
          {g.group && <div className="eyebrow mb-2 px-3">{g.group}</div>}
          <ul className="flex flex-col gap-0.5">
            {g.items.map((it) => (
              <li key={it.to}>
                <NavLink
                  to={it.to}
                  end={it.to === "/"}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    clsx(
                      "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                      isActive ? "bg-surface/80 text-ink" : "text-muted hover:bg-surface/40 hover:text-ink",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-violet shadow-[0_0_10px_rgb(139_92_246)]" />}
                      <span className={clsx(isActive ? "text-violet-soft" : "text-faint group-hover:text-muted")}>{it.icon}</span>
                      <span className="flex-1">{it.label}</span>
                      {it.preview && <span className="rounded border border-line-strong px-1 font-mono text-[9px] tracking-wider text-faint uppercase">tulossa</span>}
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function PlayerBar() {
  const { assetId, title, artist, playing, currentTime, duration, toggle, error } = usePlayer();
  if (!assetId) return null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-midnight/95 backdrop-blur lg:left-64">
      <div className="flex items-center gap-3 px-4 py-2.5">
        <button onClick={toggle} className="grid size-9 shrink-0 place-items-center rounded-full bg-violet text-white hover:bg-violet-soft" aria-label={playing ? "Tauko" : "Toista"}>
          {playing ? <Pause className="size-4" /> : <Play className="size-4 translate-x-px" />}
        </button>
        <Link to={`/tracks/${assetId}`} className="min-w-0 flex-1 hover:underline">
          <div className="truncate text-sm font-medium">{title}</div>
          <div className="truncate text-xs text-muted">{error ?? artist ?? " "}</div>
        </Link>
        <div className="font-mono text-xs text-muted tabular">
          {fmtTime(currentTime)} / {fmtTime(duration)}
        </div>
      </div>
      <div className="h-0.5 bg-surface">
        <div className="h-full bg-gradient-to-r from-violet to-cyan" style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }} />
      </div>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const hasPlayer = usePlayer((s) => s.assetId !== null);
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [loc.pathname]);
  // Space toggles playback when not typing
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.code === "Space" && !["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(t.tagName) && !t.isContentEditable) {
        e.preventDefault();
        usePlayer.getState().toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-dvh field-bg">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-violet focus:px-3 focus:py-2">
        Siirry sisältöön
      </a>
      {/* desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-line bg-obsidian/80 px-3 py-5 backdrop-blur lg:flex">
        <Link to="/" className="mb-8 flex items-center gap-2.5 px-3">
          <ResonanceMark size={30} />
          <div>
            <Wordmark className="text-sm" />
            <div className="font-mono text-[9.5px] tracking-[0.2em] text-faint uppercase">Personal Resonance Intelligence</div>
          </div>
        </Link>
        <NavList />
        <div className="mt-auto px-3 pt-6 text-2xs text-faint">
          <p className="font-display tracking-wide text-muted">Decode what moves you.</p>
          <p className="mt-1">Paikallinen tila · tiedot pysyvät koneellasi</p>
        </div>
      </aside>

      {/* mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-obsidian/90 px-4 py-3 backdrop-blur lg:hidden">
        <Link to="/" className="flex items-center gap-2">
          <ResonanceMark size={26} />
          <Wordmark className="text-xs" />
        </Link>
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-muted hover:text-ink" aria-label="Avaa valikko">
          <Menu className="size-5" />
        </button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Valikko">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 right-0 w-72 overflow-y-auto border-l border-line bg-midnight p-4 animate-fade-in">
            <div className="mb-6 flex items-center justify-between">
              <Wordmark className="text-sm" />
              <button onClick={() => setOpen(false)} className="rounded p-1 text-muted hover:text-ink" aria-label="Sulje valikko">
                <X className="size-5" />
              </button>
            </div>
            <NavList onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <main id="main" className={clsx("lg:pl-64", hasPlayer && "pb-20")}>
        <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-10 lg:py-10 animate-fade-in" key={loc.pathname}>
          {children}
        </div>
      </main>
      <PlayerBar />
    </div>
  );
}
