/**
 * RESONANCEX brand marks.
 *
 * The symbol: concentric resonance wavefronts (the field), a waveform passing
 * through it, and a single point of human perception at the centre.
 * Module icons share the same stroke language.
 */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

export function ResonanceMark({ size = 32, ...rest }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden {...rest}>
      <circle cx="32" cy="32" r="27" stroke="#8B5CF6" strokeOpacity=".22" strokeWidth="1.6" />
      <circle cx="32" cy="32" r="20" stroke="#8B5CF6" strokeOpacity=".42" strokeWidth="1.8" />
      <circle cx="32" cy="32" r="12.5" stroke="#8B5CF6" strokeOpacity=".7" strokeWidth="2" />
      <path
        d="M4 32c4.5 0 5.5-10 10-10s5.5 20 10 20 4.5-20 8-20 5.5 20 10 20 5.5-10 10-10 4.5 0 8 0"
        stroke="url(#rx-wave)"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <circle cx="32" cy="32" r="3.4" fill="#D9BB81" />
      <defs>
        <linearGradient id="rx-wave" x1="4" y1="32" x2="60" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#38BDF8" stopOpacity=".2" />
          <stop offset=".5" stopColor="#38BDF8" />
          <stop offset="1" stopColor="#D4A5F9" stopOpacity=".3" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-semibold tracking-[0.18em] text-ink ${className}`}>
      RESONANCE<span className="text-violet-soft">X</span>
    </span>
  );
}

const base = (size: number, rest: IconProps) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  ...rest,
});

/** SonicDNA — a waveform inside a resonance ring */
export function SonicIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg {...base(size, rest)}>
      <circle cx="12" cy="12" r="9.5" opacity=".45" />
      <path d="M3.5 12h2l1.5-4 2 8 2-11 2 14 2-9 1.5 4 1.5-2h2.5" />
    </svg>
  );
}

/** VisualDNA — an aperture/eye built from wavefronts */
export function VisualIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg {...base(size, rest)}>
      <path d="M2.5 12c2.6-4.4 5.9-6.5 9.5-6.5s6.9 2.1 9.5 6.5c-2.6 4.4-5.9 6.5-9.5 6.5S5.1 16.4 2.5 12Z" />
      <circle cx="12" cy="12" r="3.2" />
      <circle cx="12" cy="12" r=".6" fill="currentColor" />
    </svg>
  );
}

/** Resonance Core — interference of two wave sources */
export function CoreIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg {...base(size, rest)}>
      <circle cx="9" cy="12" r="6" opacity=".6" />
      <circle cx="15" cy="12" r="6" opacity=".6" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    </svg>
  );
}

/** Fusion Studio — sound wave becoming a frame */
export function FusionIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg {...base(size, rest)}>
      <path d="M2.5 12c1.5 0 2-3 3.5-3s2 6 3.5 6 2-3 3-3" />
      <rect x="13" y="6.5" width="8.5" height="11" rx="2" />
      <path d="m16 10 3 2-3 2Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Resonance Atlas — constellation in a field */
export function AtlasIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg {...base(size, rest)}>
      <circle cx="12" cy="12" r="9.5" opacity=".4" />
      <path d="m6.5 14.5 4-6 3.5 4.5 3.5-5" opacity=".8" />
      <circle cx="6.5" cy="14.5" r="1.3" fill="currentColor" />
      <circle cx="10.5" cy="8.5" r="1.3" fill="currentColor" />
      <circle cx="14" cy="13" r="1.3" fill="currentColor" />
      <circle cx="17.5" cy="8" r="1.3" fill="currentColor" />
    </svg>
  );
}

/** Prompt Studio — a pulse turning into text lines */
export function PromptIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg {...base(size, rest)}>
      <path d="M3 8h2l1.2-3 1.6 6 1.2-3H11" />
      <path d="M13 8h8M3 13h18M3 18h12" opacity=".75" />
    </svg>
  );
}
