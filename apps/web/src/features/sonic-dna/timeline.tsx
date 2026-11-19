import clsx from "clsx";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { BAND_COLORS, BAND_FI, fmtTime } from "@/services/format";
import { getAudioTime, usePlayer } from "@/stores/player";
import type { Analysis, Marker, Series, TimeSeries } from "@/types/api";

export const MARKER_COLORS: Record<string, string> = {
  body_reaction: "#8B5CF6",
  chills: "#38BDF8",
  emotional_peak: "#D4A5F9",
  favorite_rhythm: "#6EE7B7",
  important_harmony: "#D9BB81",
  unpleasant: "#F87171",
  unexpected: "#FBBF24",
  symbolism: "#F5F3FF",
};
const SEG_COLORS = ["#8B5CF6", "#38BDF8", "#D4A5F9", "#D9BB81", "#6EE7B7", "#F472B6", "#A3E635", "#FB923C"];

export function valueAt(series: Series, dt: number, t: number): number | null {
  const i = Math.floor(t / dt);
  if (i < 0 || i >= series.length) return null;
  return series[i];
}

function valueAtXY(ts: { t: Series; v: Series }, t: number): number | null {
  let best: number | null = null;
  let bd = Infinity;
  for (let i = 0; i < ts.t.length; i++) {
    const tt = ts.t[i];
    if (tt === null) continue;
    const d = Math.abs(tt - t);
    if (d < bd) {
      bd = d;
      best = ts.v[i];
    }
  }
  return best;
}

type DrawFn = (ctx: CanvasRenderingContext2D, w: number, h: number, toX: (t: number) => number, view: { start: number; end: number }) => void;

/** Generic canvas lane bound to the shared timeline view. */
function Lane({ label, height, draw, deps, hover, duration, sub }: { label: string; height: number; draw: DrawFn; deps: unknown[]; hover?: (t: number) => ReactNode; duration: number; sub?: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const head = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const view = usePlayer((s) => s.view);
  const selection = usePlayer((s) => s.selection);
  const [hoverX, setHoverX] = useState<number | null>(null);
  const drag = useRef<{ x0: number; moved: boolean } | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const span = Math.max(1e-6, view.end - view.start);
  const toX = (t: number) => ((t - view.start) / span) * width;
  const toT = (x: number) => view.start + (x / Math.max(1, width)) * span;

  useEffect(() => {
    const c = canvas.current;
    if (!c || !width) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = width * dpr;
    c.height = height * dpr;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    draw(ctx, width, height, toX, view);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height, view.start, view.end, ...deps]);

  // playhead (no React re-render per frame)
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      const x = toX(getAudioTime());
      if (head.current) {
        head.current.style.transform = `translateX(${x}px)`;
        head.current.style.opacity = x >= 0 && x <= width ? "1" : "0";
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.start, view.end, width]);

  // wheel zoom / pan (non-passive)
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      const st = usePlayer.getState();
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const r = el.getBoundingClientRect();
        const t = st.view.start + ((e.clientX - r.left) / r.width) * (st.view.end - st.view.start);
        st.zoom(e.deltaY > 0 ? 1.25 : 0.8, t);
      } else if (e.shiftKey) {
        e.preventDefault();
        const sp = st.view.end - st.view.start;
        const dt = (e.deltaY || e.deltaX) > 0 ? sp * 0.1 : -sp * 0.1;
        st.setView({ start: st.view.start + dt, end: st.view.end + dt });
      }
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const selX = selection ? [toX(selection.start), toX(selection.end)] : null;

  return (
    <div className="grid grid-cols-[72px_1fr] items-stretch sm:grid-cols-[96px_1fr]">
      <div className="flex flex-col justify-center border-r border-line pr-2 text-right">
        <div className="text-[10px] leading-tight break-words text-muted [hyphens:auto] sm:text-[11px]" lang="fi">{label}</div>
        {sub && <div className="hidden font-mono text-[9px] text-faint sm:block">{sub}</div>}
      </div>
      <div ref={wrap} className="relative touch-none" style={{ height }}>
        <canvas
          ref={canvas}
          style={{ width: "100%", height }}
          className="block cursor-crosshair"
          onPointerDown={(e) => {
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
            drag.current = { x0: e.nativeEvent.offsetX, moved: false };
          }}
          onPointerMove={(e) => {
            const x = e.nativeEvent.offsetX;
            setHoverX(x);
            if (drag.current && Math.abs(x - drag.current.x0) > 4) {
              drag.current.moved = true;
              const a = toT(Math.min(x, drag.current.x0));
              const b = toT(Math.max(x, drag.current.x0));
              usePlayer.getState().setSelection({ start: Math.max(0, a), end: Math.min(duration, b) });
            }
          }}
          onPointerUp={(e) => {
            if (drag.current && !drag.current.moved) {
              usePlayer.getState().seek(toT(e.nativeEvent.offsetX));
              usePlayer.getState().setSelection(null);
            }
            drag.current = null;
          }}
          onPointerLeave={() => setHoverX(null)}
        />
        {selX && <div className="pointer-events-none absolute inset-y-0 border-x border-cyan/60 bg-cyan/10" style={{ left: Math.max(0, selX[0]), width: Math.max(1, Math.min(width, selX[1]) - Math.max(0, selX[0])) }} />}
        <div ref={head} className="pointer-events-none absolute inset-y-0 left-0 w-px bg-ink shadow-[0_0_8px_rgb(245_243_255/0.8)]" />
        {hoverX !== null && hover && (
          <>
            <div className="pointer-events-none absolute inset-y-0 w-px bg-cyan/40" style={{ left: hoverX }} />
            <div className="pointer-events-none absolute top-1 z-10 rounded border border-line-strong bg-midnight/95 px-2 py-1 font-mono text-[10px] whitespace-nowrap text-ink shadow-lg" style={{ left: Math.min(hoverX + 8, Math.max(0, width - 170)) }}>
              {fmtTime(toT(hoverX), true)} · {hover(toT(hoverX))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function drawLine(ctx: CanvasRenderingContext2D, series: Series, dt: number, toX: (t: number) => number, toY: (v: number) => number, view: { start: number; end: number }, color: string, width = 1.5, fill?: string, h?: number) {
  const i0 = Math.max(0, Math.floor(view.start / dt) - 1);
  const i1 = Math.min(series.length - 1, Math.ceil(view.end / dt) + 1);
  ctx.beginPath();
  let started = false;
  let firstX = 0;
  let lastX = 0;
  for (let i = i0; i <= i1; i++) {
    const v = series[i];
    if (v === null || v === undefined) continue;
    const x = toX(i * dt + dt / 2);
    const y = toY(v);
    if (!started) {
      ctx.moveTo(x, y);
      firstX = x;
      started = true;
    } else ctx.lineTo(x, y);
    lastX = x;
  }
  if (fill && h !== undefined && started) {
    ctx.lineTo(lastX, h);
    ctx.lineTo(firstX, h);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    // redraw stroke on top
    ctx.beginPath();
    started = false;
    for (let i = i0; i <= i1; i++) {
      const v = series[i];
      if (v === null || v === undefined) continue;
      const x = toX(i * dt + dt / 2);
      if (!started) {
        ctx.moveTo(x, toY(v));
        started = true;
      } else ctx.lineTo(x, toY(v));
    }
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineJoin = "round";
  ctx.stroke();
}

export function Timeline({ analysis, ts, markers, spectrogramUrl }: { analysis: Analysis; ts: TimeSeries; markers: Marker[]; spectrogramUrl: string }) {
  const duration = ts.duration;
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const segs = analysis.segments;
  const chords = analysis.summary.tonality.chords;
  useEffect(() => {
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = spectrogramUrl;
  }, [spectrogramUrl]);

  const wf = ts.waveform;
  const bucketDt = duration / wf.buckets;

  return (
    <div className="flex flex-col gap-px overflow-hidden rounded-xl border border-line bg-obsidian/70">
      <Overview ts={ts} duration={duration} />
      <Lane
        label="Aaltomuoto"
        height={72}
        duration={duration}
        deps={[ts]}
        hover={(t) => {
          const v = valueAt(ts.rms_db, ts.dt, t);
          return v === null ? "" : `RMS ${v.toFixed(1)} dBFS`;
        }}
        draw={(ctx, w, h, _toX, view) => {
          const mid = h / 2;
          const grad = ctx.createLinearGradient(0, 0, w, 0);
          grad.addColorStop(0, "#8B5CF6");
          grad.addColorStop(1, "#38BDF8");
          ctx.fillStyle = grad;
          const span = view.end - view.start;
          for (let x = 0; x < w; x++) {
            const t0 = view.start + (x / w) * span;
            const t1 = view.start + ((x + 1) / w) * span;
            const b0 = Math.max(0, Math.floor(t0 / bucketDt));
            const b1 = Math.min(wf.buckets - 1, Math.max(b0, Math.ceil(t1 / bucketDt) - 1));
            let lo = 0;
            let hi = 0;
            for (let b = b0; b <= b1; b++) {
              lo = Math.min(lo, wf.min[b] ?? 0);
              hi = Math.max(hi, wf.max[b] ?? 0);
            }
            ctx.fillRect(x, mid - hi * mid * 0.95, 1, Math.max(1, (hi - lo) * mid * 0.95));
          }
          ctx.fillStyle = "rgba(245,243,255,0.25)";
          for (const b of ts.beats) {
            if (b < view.start || b > view.end) continue;
            ctx.fillRect(((b - view.start) / span) * w, h - 4, 1, 4);
          }
        }}
      />
      <Lane
        label="Spektrogrammi"
        sub="mel · 0–11 kHz"
        height={110}
        duration={duration}
        deps={[img]}
        hover={(t) => {
          const c = valueAt(ts.centroid_hz, ts.dt, t);
          return c === null ? "" : `sentroidi ${Math.round(c)} Hz`;
        }}
        draw={(ctx, w, h, _toX, view) => {
          if (!img) return;
          const sx = (view.start / duration) * img.width;
          const sw = ((view.end - view.start) / duration) * img.width;
          ctx.imageSmoothingEnabled = true;
          ctx.drawImage(img, sx, 0, Math.max(1, sw), img.height, 0, 0, w, h);
        }}
      />
      <Lane
        label="Taajuuskaistat"
        sub="dB suht. huippuun"
        height={120}
        duration={duration}
        deps={[ts]}
        hover={(t) =>
          Object.keys(ts.bands)
            .map((k) => `${BAND_FI[k]} ${(valueAt(ts.bands[k], ts.dt, t) ?? NaN).toFixed(0)}`)
            .join(" · ")
        }
        draw={(ctx, w, h, toX, view) => {
          const keys = ["treble", "mid", "low_mid", "bass", "sub_bass"];
          const rowH = h / keys.length;
          keys.forEach((k, i) => {
            const top = i * rowH;
            const toY = (v: number) => top + rowH - Math.max(0, Math.min(1, (v + 60) / 60)) * (rowH - 2);
            drawLine(ctx, ts.bands[k], ts.dt, toX, toY, view, BAND_COLORS[k], 1.2, BAND_COLORS[k] + "33", top + rowH);
            ctx.fillStyle = "rgba(156,169,190,0.55)";
            ctx.font = "9px JetBrains Mono, monospace";
            ctx.fillText(BAND_FI[k], 4, top + 10);
            ctx.fillStyle = "rgba(156,169,190,0.07)";
            ctx.fillRect(0, top + rowH - 0.5, w, 0.5);
          });
        }}
      />
      <Lane
        label="Energia"
        sub="5 s & hetkellinen"
        height={84}
        duration={duration}
        deps={[ts]}
        hover={(t) => {
          const e = valueAt(ts.energy_env_db, ts.dt, t);
          const o = valueAt(ts.onset_strength, ts.dt, t);
          return `energia ${e?.toFixed(1)} dB · iskut ${o?.toFixed(2)}`;
        }}
        draw={(ctx, w, h, toX, view) => {
          const vals = ts.rms_db.filter((v): v is number => v !== null && v > -79);
          const lo = vals.length ? Math.min(...vals) : -60;
          const hi = vals.length ? Math.max(...vals) : 0;
          const toY = (v: number) => h - 4 - ((v - lo) / Math.max(1, hi - lo)) * (h - 10);
          drawLine(ctx, ts.rms_db, ts.dt, toX, toY, view, "rgba(139,92,246,0.35)", 1, "rgba(139,92,246,0.10)", h);
          drawLine(ctx, ts.energy_env_db, ts.dt, toX, toY, view, "#D4A5F9", 2);
          const toYo = (v: number) => h - v * 18;
          ctx.globalAlpha = 0.6;
          drawLine(ctx, ts.onset_strength, ts.dt, toX, toYo, view, "#38BDF8", 0.8);
          ctx.globalAlpha = 1;
          for (const p of analysis.summary.structure.peak_moments) {
            if (p.time < view.start || p.time > view.end) continue;
            const x = toX(p.time);
            ctx.fillStyle = p.kind === "sudden_rise" ? "#FBBF24" : "#D9BB81";
            ctx.beginPath();
            ctx.moveTo(x, 3);
            ctx.lineTo(x + 4, 8);
            ctx.lineTo(x, 13);
            ctx.lineTo(x - 4, 8);
            ctx.fill();
          }
          void w;
        }}
      />
      <Lane
        label="Tempo"
        sub="paikallinen BPM"
        height={56}
        duration={duration}
        deps={[ts]}
        hover={(t) => {
          const v = valueAt(ts.local_tempo, ts.local_tempo_dt, t);
          return v === null ? "" : `${v.toFixed(1)} BPM (8 s ikkuna)`;
        }}
        draw={(ctx, w, h, toX, view) => {
          const vals = ts.local_tempo.filter((v): v is number => v !== null);
          if (!vals.length) return;
          const lo = Math.min(...vals) - 4;
          const hi = Math.max(...vals) + 4;
          const toY = (v: number) => h - 6 - ((v - lo) / Math.max(1, hi - lo)) * (h - 14);
          drawLine(ctx, ts.local_tempo, ts.local_tempo_dt, toX, toY, view, "#38BDF8", 1.6);
          ctx.fillStyle = "rgba(156,169,190,0.6)";
          ctx.font = "9px JetBrains Mono, monospace";
          ctx.fillText(`${hi.toFixed(0)}`, w - 26, 10);
          ctx.fillText(`${lo.toFixed(0)}`, w - 26, h - 3);
        }}
      />
      <Lane
        label="Harmonia"
        sub="kroma · soinnut · jännite"
        height={104}
        duration={duration}
        deps={[ts, chords]}
        hover={(t) => {
          const ch = chords.find((c) => c.start <= t && c.end > t);
          const ten = valueAtXY(ts.tension, t);
          return `${ch ? `sointu ${ch.label === "N" ? "–" : ch.label}` : ""}${ten !== null ? ` · jännite ${ten.toFixed(2)}` : ""}`;
        }}
        draw={(ctx, w, h, toX, view) => {
          const rows = 12;
          const top = 16;
          const rowH = (h - top) / rows;
          const cd = ts.chroma.dt;
          const i0 = Math.max(0, Math.floor(view.start / cd));
          const i1 = Math.min(ts.chroma.values[0].length - 1, Math.ceil(view.end / cd));
          for (let r = 0; r < rows; r++) {
            const row = ts.chroma.values[r];
            for (let i = i0; i <= i1; i++) {
              const v = row[i] ?? 0;
              if (v < 0.15) continue;
              const x0 = toX(i * cd);
              const x1 = toX((i + 1) * cd);
              ctx.fillStyle = `rgba(212,165,249,${Math.pow(v, 2) * 0.85})`;
              ctx.fillRect(x0, h - (r + 1) * rowH, Math.max(1, x1 - x0), rowH - 0.5);
            }
          }
          ctx.fillStyle = "rgba(156,169,190,0.5)";
          ctx.font = "8px JetBrains Mono, monospace";
          ["C", "D", "E", "F", "G", "A", "B"].forEach((n) => {
            const idx = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[n]!;
            ctx.fillText(n, 2, h - idx * rowH - 2);
          });
          // chord labels
          ctx.font = "10px JetBrains Mono, monospace";
          for (const c of chords) {
            if (c.end < view.start || c.start > view.end || c.label === "N") continue;
            const x0 = toX(c.start);
            const x1 = toX(c.end);
            if (x1 - x0 < 18) continue;
            ctx.fillStyle = "rgba(245,243,255,0.85)";
            ctx.fillText(c.label, Math.max(2, x0 + 3), 11);
            ctx.fillStyle = "rgba(156,169,190,0.25)";
            ctx.fillRect(x0, 0, 1, top - 2);
          }
          // tension
          ctx.beginPath();
          let st = false;
          for (let i = 0; i < ts.tension.t.length; i++) {
            const t = ts.tension.t[i];
            const v = ts.tension.v[i];
            if (t === null || v === null || t < view.start - 5 || t > view.end + 5) continue;
            const x = toX(t);
            const y = h - v * (h - top) * 1.6;
            if (!st) {
              ctx.moveTo(x, y);
              st = true;
            } else ctx.lineTo(x, y);
          }
          ctx.strokeStyle = "#D9BB81";
          ctx.lineWidth = 1.3;
          ctx.stroke();
          void w;
        }}
      />
      <Lane
        label="Rakenne"
        sub="ehdotettu · likimääräinen"
        height={52}
        duration={duration}
        deps={[segs]}
        hover={(t) => {
          const s = segs.find((x) => x.start <= t && x.end > t);
          return s ? `${s.letter} · ${ROLE_FI[s.role] ?? s.role} · ${s.relative_energy_db > 0 ? "+" : ""}${s.relative_energy_db.toFixed(1)} dB` : "";
        }}
        draw={(ctx, _w, h, toX) => {
          const letters = [...new Set(segs.map((s) => s.letter))].sort();
          for (const s of segs) {
            const x0 = toX(s.start);
            const x1 = toX(s.end);
            const col = SEG_COLORS[letters.indexOf(s.letter) % SEG_COLORS.length];
            ctx.fillStyle = col + "33";
            ctx.fillRect(x0 + 1, 6, Math.max(1, x1 - x0 - 2), h - 12);
            ctx.fillStyle = col;
            ctx.fillRect(x0 + 1, 6, Math.max(1, x1 - x0 - 2), 2);
            if (x1 - x0 > 40) {
              ctx.fillStyle = "rgba(245,243,255,0.9)";
              ctx.font = "600 11px Space Grotesk, sans-serif";
              ctx.fillText(s.letter, x0 + 6, 24);
              ctx.fillStyle = "rgba(156,169,190,0.9)";
              ctx.font = "10px Inter, sans-serif";
              ctx.fillText(ROLE_FI[s.role] ?? s.role, x0 + 6, 38, x1 - x0 - 10);
            }
          }
        }}
      />
      <Lane
        label="Omat merkinnät"
        height={40}
        duration={duration}
        deps={[markers]}
        hover={(t) => {
          const m = markers.find((x) => Math.abs(x.start_seconds - t) < 1.5 || (x.end_seconds && x.start_seconds <= t && x.end_seconds >= t));
          return m ? `${MARKER_FI[m.label] ?? m.label}${m.note ? ` – ${m.note.slice(0, 40)}` : ""}` : "";
        }}
        draw={(ctx, _w, h, toX) => {
          for (const m of markers) {
            const col = MARKER_COLORS[m.label] ?? "#F5F3FF";
            const x0 = toX(m.start_seconds);
            if (m.end_seconds) {
              ctx.fillStyle = col + "30";
              ctx.fillRect(x0, 4, toX(m.end_seconds) - x0, h - 8);
            }
            ctx.fillStyle = col;
            ctx.fillRect(x0 - 1, 4, 2, h - 8);
            ctx.beginPath();
            ctx.moveTo(x0, 4);
            ctx.lineTo(x0 + 9, 8);
            ctx.lineTo(x0, 12);
            ctx.fill();
          }
        }}
      />
    </div>
  );
}

export const ROLE_FI: Record<string, string> = {
  intro: "Intro",
  outro: "Outro",
  climax: "Huipennus",
  breakdown: "Breakdown",
  drop: "Drop",
  build: "Nousu",
  repeated: "Toistuva",
  section: "Osa",
};

export const MARKER_FI: Record<string, string> = {
  body_reaction: "Voimakas kehollinen reaktio",
  chills: "Kylmät väreet",
  emotional_peak: "Tunnehuippu",
  favorite_rhythm: "Lempirytmi",
  important_harmony: "Tärkeä harmonia",
  unpleasant: "Epämiellyttävä kohta",
  unexpected: "Odottamaton vaikutus",
  symbolism: "Henkilökohtainen symboliikka",
};

/** Full-track minimap with a draggable view window. */
function Overview({ ts, duration }: { ts: TimeSeries; duration: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const view = usePlayer((s) => s.view);
  const dragging = useRef<number | null>(null);
  const h = 28;
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);
  useEffect(() => {
    const c = ref.current;
    if (!c || !w) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = w * dpr;
    c.height = h * dpr;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const vals = ts.energy_env_db;
    const fin = vals.filter((v): v is number => v !== null && v > -79);
    const lo = Math.min(...fin);
    const hi = Math.max(...fin);
    ctx.fillStyle = "rgba(139,92,246,0.45)";
    for (let x = 0; x < w; x++) {
      const v = vals[Math.floor((x / w) * vals.length)] ?? lo;
      const hh = ((v - lo) / Math.max(1, hi - lo)) * (h - 4);
      ctx.fillRect(x, h - hh, 1, hh);
    }
  }, [w, ts]);
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      if (head.current && duration) head.current.style.transform = `translateX(${(getAudioTime() / duration) * w}px)`;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [w, duration]);
  const full = view.start <= 0.01 && view.end >= duration - 0.01;
  const move = (clientX: number) => {
    const r = wrap.current!.getBoundingClientRect();
    const t = ((clientX - r.left) / r.width) * duration;
    const span = view.end - view.start;
    usePlayer.getState().setView({ start: t - span / 2, end: t + span / 2 });
  };
  return (
    <div className="grid grid-cols-[72px_1fr] sm:grid-cols-[96px_1fr]">
      <div className="flex items-center justify-end border-r border-line pr-2 text-right text-[10px] leading-tight text-muted sm:text-[11px]">Koko kappale</div>
      <div
        ref={wrap}
        className={clsx("relative touch-none", !full && "cursor-grab")}
        style={{ height: h }}
        onPointerDown={(e) => {
          if (full) {
            const r = wrap.current!.getBoundingClientRect();
            usePlayer.getState().seek(((e.clientX - r.left) / r.width) * duration);
            return;
          }
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
          dragging.current = e.clientX;
          move(e.clientX);
        }}
        onPointerMove={(e) => dragging.current !== null && move(e.clientX)}
        onPointerUp={() => (dragging.current = null)}
      >
        <canvas ref={ref} style={{ width: "100%", height: h }} className="block" />
        {!full && <div className="pointer-events-none absolute inset-y-0 rounded-sm border border-cyan/70 bg-cyan/10" style={{ left: (view.start / duration) * w, width: ((view.end - view.start) / duration) * w }} />}
        <div ref={head} className="pointer-events-none absolute inset-y-0 left-0 w-px bg-ink/80" />
      </div>
    </div>
  );
}
