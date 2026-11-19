import type { FeatureDef } from "@/types/api";

export function fmtTime(s: number | null | undefined, withTenths = false): string {
  if (s === null || s === undefined || !Number.isFinite(s)) return "–:––";
  const m = Math.floor(s / 60);
  const sec = s - m * 60;
  if (withTenths) return `${m}:${sec.toFixed(1).padStart(4, "0")}`;
  return `${m}:${Math.floor(sec).toString().padStart(2, "0")}`;
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} t`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} kt`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} Mt`;
  return `${(n / 1024 ** 3).toFixed(2)} Gt`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("fi-FI", { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  return v.toLocaleString("fi-FI", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

/** Mirrors backend fmt_value (resonance_core.core). */
export function fmtFeature(def: FeatureDef | undefined, key: string, v: number | null | undefined): string {
  if (v === null || v === undefined) return "–";
  const unit = def?.unit ?? "";
  if (key === "tempo_bpm") return `${v.toFixed(0)} BPM`;
  if (key === "major_mode") return v >= 0.5 ? "duuri" : "molli";
  if (unit === "osuus") return `${(v * 100).toFixed(1)} %`;
  if (unit === "Hz") return `${Math.round(v).toLocaleString("fi-FI")} Hz`;
  if (unit === "LUFS" || unit === "LU" || unit === "dB") return `${v.toFixed(1)} ${unit}`;
  if (unit === "s") return `${v.toFixed(0)} s`;
  if (unit === "/min" || unit === "iskua/s") return `${v.toFixed(2)} ${unit}`;
  return v.toFixed(2);
}

export const STAGE_FI: Record<string, string> = {
  decode: "Dekoodaus",
  rhythm: "Rytmi ja tempo",
  spectral: "Spektri ja taajuuskaistat",
  tonality: "Sävellaji ja harmonia",
  dynamics: "Dynamiikka ja äänekkyys",
  structure: "Rakenne ja energiakaari",
  render: "Visualisoinnit",
};

export const BAND_FI: Record<string, string> = {
  sub_bass: "Sub-basso",
  bass: "Basso",
  low_mid: "Alakeski",
  mid: "Keskiäänet",
  treble: "Diskantti",
};

export const BAND_COLORS: Record<string, string> = {
  sub_bass: "#8B5CF6",
  bass: "#A78BFA",
  low_mid: "#D4A5F9",
  mid: "#38BDF8",
  treble: "#D9BB81",
};

export const MODE_FI: Record<string, string> = {
  deep_resonance: "Syvä resonanssi",
  intensification: "Tunteen voimistaminen",
  unknown_territory: "Tuntematon alue",
};
