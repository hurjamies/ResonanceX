import clsx from "clsx";
import { Check, Copy, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { EvidenceLevel } from "@/types/api";

// -------------------------------------------------------------------- Button
type Variant = "primary" | "secondary" | "ghost" | "danger";
export function Button({
  variant = "secondary",
  size = "md",
  className,
  loading,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-violet text-white hover:bg-violet-soft shadow-[0_0_24px_-8px_rgb(139_92_246/0.8)]",
        variant === "secondary" && "border border-line-strong bg-surface/60 text-ink hover:border-violet/60 hover:bg-surface",
        variant === "ghost" && "text-muted hover:bg-surface/70 hover:text-ink",
        variant === "danger" && "border border-danger/40 text-danger hover:bg-danger/10",
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

// --------------------------------------------------------------------- Panel
export function Panel({ title, eyebrow, actions, children, className, bodyClass }: { title?: ReactNode; eyebrow?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string }) {
  return (
    <section className={clsx("panel", className)}>
      {(title || actions || eyebrow) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx("p-4 sm:p-5", bodyClass)}>{children}</div>
    </section>
  );
}

// -------------------------------------------------------------------- Badges
const EVIDENCE_STYLE: Record<EvidenceLevel, string> = {
  insufficient: "border-line-strong text-faint",
  observation: "border-cyan/30 text-cyan",
  preliminary: "border-violet/40 text-violet-soft",
  supported: "border-gold/50 text-gold",
};
const EVIDENCE_LABEL: Record<EvidenceLevel, string> = {
  insufficient: "Ei riittävästi näyttöä",
  observation: "Havainto",
  preliminary: "Alustava hypoteesi",
  supported: "Toistuvasti tuettu",
};
const EVIDENCE_BARS: Record<EvidenceLevel, number> = { insufficient: 0, observation: 1, preliminary: 2, supported: 3 };

export function EvidenceBadge({ level, className }: { level: EvidenceLevel; className?: string }) {
  const n = EVIDENCE_BARS[level];
  return (
    <span
      className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-medium whitespace-nowrap", EVIDENCE_STYLE[level], className)}
      title="Näytön taso perustuu havaintojen määrään, johdonmukaisuuteen ja tilastolliseen testaukseen – ei kielimallin arvioon."
    >
      <span className="flex items-end gap-px" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={clsx("w-[3px] rounded-sm", i <= n ? "bg-current" : "bg-current opacity-20")} style={{ height: 3 + i * 2 }} />
        ))}
      </span>
      {EVIDENCE_LABEL[level]}
    </span>
  );
}

export type Category = "measured" | "estimated" | "model" | "self_reported" | "statistical" | "interpretive";
const CAT: Record<Category, [string, string]> = {
  measured: ["Mitattu", "text-cyan border-cyan/25"],
  estimated: ["Algoritminen arvio", "text-lavender border-lavender/25"],
  model: ["Mallin ennuste", "text-violet-soft border-violet/30"],
  self_reported: ["Oma kokemus", "text-gold border-gold/30"],
  statistical: ["Tilastollinen yhteys", "text-ok border-ok/25"],
  interpretive: ["Tulkinta / hypoteesi", "text-muted border-line-strong"],
};
const CAT_HELP: Record<Category, string> = {
  measured: "Suoraan signaalista laskettu ominaisuus.",
  estimated: "Algoritminen arvio, johon liittyy epävarmuutta.",
  model: "Koneoppimismallin tuottama luokitteluhypoteesi.",
  self_reported: "Oma raporttisi – ei fysiologinen mittaus.",
  statistical: "Havaittu yhteys aineistossasi – ei syy-yhteys.",
  interpretive: "Luova tai tulkitseva hypoteesi.",
};
export function CategoryBadge({ cat, className }: { cat: Category; className?: string }) {
  return (
    <span title={CAT_HELP[cat]} className={clsx("inline-flex items-center rounded border px-1.5 py-px font-mono text-[10px] uppercase tracking-wider", CAT[cat][1], className)}>
      {CAT[cat][0]}
    </span>
  );
}

export function Chip({ active, onClick, children, className }: { active?: boolean; onClick?: () => void; children: ReactNode; className?: string }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={clsx(
        "rounded-full border px-3 py-1 text-xs transition-colors",
        active ? "border-violet/70 bg-violet/15 text-ink glow-violet" : "border-line-strong text-muted hover:border-violet/40 hover:text-ink",
        className,
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------- Stat
export function Stat({ label, value, hint, accent }: { label: string; value: ReactNode; hint?: ReactNode; accent?: "violet" | "cyan" | "gold" }) {
  return (
    <div className="min-w-0">
      <div className="eyebrow truncate">{label}</div>
      <div className={clsx("mt-1 font-display text-2xl font-semibold tabular", accent === "violet" && "text-violet-soft", accent === "cyan" && "text-cyan", accent === "gold" && "text-gold")}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- CopyButton
export function CopyButton({ text, label = "Kopioi", className, size = "sm" }: { text: string; label?: string; className?: string; size?: "sm" | "md" }) {
  const [state, setState] = useState<"idle" | "ok" | "err">("idle");
  useEffect(() => {
    if (state === "idle") return;
    const t = setTimeout(() => setState("idle"), 1600);
    return () => clearTimeout(t);
  }, [state]);
  const copy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      setState("ok");
    } catch {
      setState("err");
    }
  };
  return (
    <Button type="button" size={size} variant="ghost" onClick={copy} className={className} aria-label={`${label}`}>
      {state === "ok" ? <Check className="size-3.5 text-ok" /> : state === "err" ? <X className="size-3.5 text-danger" /> : <Copy className="size-3.5" />}
      <span>{state === "ok" ? "Kopioitu" : state === "err" ? "Epäonnistui" : label}</span>
    </Button>
  );
}

// ------------------------------------------------------------- RatingSlider
/** 0–10 rating that can be left unset ("ohitettu"). */
export function RatingSlider({ label, hint, value, onChange }: { label: string; hint?: string; value: number | null | undefined; onChange: (v: number | null) => void }) {
  const set = value !== null && value !== undefined;
  const id = useRef(`r-${Math.random().toString(36).slice(2)}`).current;
  return (
    <div className="group">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <label htmlFor={id} className={clsx("text-sm", set ? "text-ink" : "text-muted")} title={hint || undefined}>
          {label}
        </label>
        <div className="flex items-center gap-2">
          <span className={clsx("w-6 text-right font-mono text-sm tabular", set ? "text-violet-soft" : "text-faint")}>{set ? value : "–"}</span>
          {set && (
            <button type="button" onClick={() => onChange(null)} className="text-2xs text-faint hover:text-ink" aria-label={`Tyhjennä ${label}`}>
              ohita
            </button>
          )}
        </div>
      </div>
      <input
        id={id}
        type="range"
        min={0}
        max={10}
        step={1}
        value={set ? value : 5}
        onChange={(e) => onChange(Number(e.target.value))}
        onClick={(e) => !set && onChange(Number((e.target as HTMLInputElement).value))}
        className={clsx("w-full", !set && "opacity-35")}
        aria-valuetext={set ? `${value} / 10` : "ei arvioitu"}
      />
    </div>
  );
}

// ------------------------------------------------------------------- Empty
export function Empty({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && <div className="mb-4 text-violet-soft">{icon}</div>}
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-2 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <Loader2 className="size-4 animate-spin text-violet-soft" />
      {label ?? "Ladataan…"}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{error instanceof Error ? error.message : String(error)}</div>;
}

// ------------------------------------------------------------------- Modal
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // Escape: close through React state. Some Chromium builds close the dialog on
      // "cancel" without a following "close" event, leaving `open` stuck at true.
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => e.target === ref.current && onClose()}
      className={clsx("m-auto w-[calc(100%-2rem)] rounded-2xl border border-line-strong bg-midnight p-0 text-ink backdrop:bg-black/60 backdrop:backdrop-blur-sm", wide ? "max-w-4xl" : "max-w-lg")}
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 className="text-base font-semibold">{title}</h2>
        <button onClick={onClose} className="rounded p-1 text-muted hover:text-ink" aria-label="Sulje">
          <X className="size-4" />
        </button>
      </div>
      <div className="max-h-[75vh] overflow-y-auto p-5">{open && children}</div>
    </dialog>
  );
}

// -------------------------------------------------------------------- Tabs
export function Tabs<T extends string>({ tabs, value, onChange, className }: { tabs: { key: T; label: ReactNode }[]; value: T; onChange: (k: T) => void; className?: string }) {
  return (
    <div role="tablist" className={clsx("flex gap-1 overflow-x-auto rounded-lg border border-line bg-obsidian/60 p-1", className)}>
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={clsx("rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors", value === t.key ? "bg-surface text-ink" : "text-muted hover:text-ink")}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions, icon }: { eyebrow?: string; title: ReactNode; description?: ReactNode; actions?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && (
          <div className="eyebrow mb-2 flex items-center gap-2">
            {icon}
            {eyebrow}
          </div>
        )}
        <h1 className="text-2xl font-semibold sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
