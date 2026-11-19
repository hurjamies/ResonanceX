import { useEffect, useMemo, useRef, useState } from "react";

export interface FieldDatum {
  id: number;
  x: number; // arbitrary units – normalised internally
  y: number;
  /** 0–10 self-reported resonance, null = not rated */
  intensity: number | null;
  label: string;
  sublabel?: string;
  origin?: string;
}

interface Props {
  data: FieldDatum[];
  height?: number;
  xLabel?: string;
  yLabel?: string;
  onSelect?: (id: number) => void;
  selectedId?: number | null;
  animate?: boolean;
  caption?: string;
}

/**
 * The Resonance Field – ResonanceX's signature visualisation.
 *
 * Each analysed item sits at a position given by a declared, reproducible
 * method (feature axes or PCA). Rated items emit wavefronts whose amplitude
 * follows the user's reported resonance; where items lie close together their
 * wavefronts interfere. It is a feature-space view – not a map of the mind.
 */
export function ResonanceField({ data, height = 360, xLabel, yLabel, onSelect, selectedId, animate = true, caption }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [hover, setHover] = useState<{ d: FieldDatum; px: number; py: number } | null>(null);
  const reduced = useMemo(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(240, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pts = useMemo(() => {
    if (!data.length) return [];
    const xs = data.map((d) => d.x);
    const ys = data.map((d) => d.y);
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    const pad = 44;
    return data.map((d) => ({
      d,
      px: pad + (x1 > x0 ? (d.x - x0) / (x1 - x0) : 0.5) * (width - 2 * pad),
      py: height - pad - (y1 > y0 ? (d.y - y0) / (y1 - y0) : 0.5) * (height - 2 * pad),
    }));
  }, [data, width, height]);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = width * dpr;
    c.height = height * dpr;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    let raf = 0;
    const start = performance.now();
    const draw = (now: number) => {
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, width, height);
      // faint grid
      ctx.strokeStyle = "rgba(156,169,190,0.06)";
      ctx.lineWidth = 1;
      for (let gx = 0; gx < width; gx += 40) {
        ctx.beginPath();
        ctx.moveTo(gx + 0.5, 0);
        ctx.lineTo(gx + 0.5, height);
        ctx.stroke();
      }
      for (let gy = 0; gy < height; gy += 40) {
        ctx.beginPath();
        ctx.moveTo(0, gy + 0.5);
        ctx.lineTo(width, gy + 0.5);
        ctx.stroke();
      }
      // wavefronts
      ctx.globalCompositeOperation = "lighter";
      for (const p of pts) {
        const r = p.d.intensity;
        if (r === null) continue;
        const amp = Math.max(0.05, r / 10);
        const rings = 4;
        for (let i = 0; i < rings; i++) {
          const phase = animate && !reduced ? ((t * 0.35 + i / rings) % 1) : (i + 0.5) / rings;
          const rad = 8 + phase * (40 + amp * 90);
          const alpha = (1 - phase) * 0.28 * amp;
          ctx.strokeStyle = p.d.origin === "generated" ? `rgba(217,187,129,${alpha})` : `rgba(139,92,246,${alpha})`;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.arc(p.px, p.py, rad, 0, Math.PI * 2);
          ctx.stroke();
        }
        const g = ctx.createRadialGradient(p.px, p.py, 0, p.px, p.py, 30 + amp * 40);
        g.addColorStop(0, `rgba(56,189,248,${0.12 * amp})`);
        g.addColorStop(1, "rgba(56,189,248,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.px, p.py, 30 + amp * 40, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      // points
      for (const p of pts) {
        const sel = p.d.id === selectedId;
        const rated = p.d.intensity !== null;
        ctx.beginPath();
        ctx.arc(p.px, p.py, sel ? 6.5 : rated ? 4.5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = !rated ? "rgba(156,169,190,0.55)" : p.d.origin === "generated" ? "#D9BB81" : "#F5F3FF";
        ctx.fill();
        if (sel) {
          ctx.strokeStyle = "#38BDF8";
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }
      if (animate && !reduced && pts.some((p) => p.d.intensity !== null)) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [pts, width, height, selectedId, animate, reduced]);

  const nearest = (mx: number, my: number) => {
    let best: (typeof pts)[number] | null = null;
    let bd = 18 * 18;
    for (const p of pts) {
      const d2 = (p.px - mx) ** 2 + (p.py - my) ** 2;
      if (d2 < bd) {
        bd = d2;
        best = p;
      }
    }
    return best;
  };

  return (
    <figure ref={wrapRef} className="relative w-full select-none">
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height }}
        className={`block rounded-xl bg-obsidian/70 ${onSelect ? "cursor-pointer" : ""}`}
        role="img"
        aria-label={`Resonanssikenttä: ${data.length} kohdetta${xLabel ? `, vaaka-akseli ${xLabel}` : ""}${yLabel ? `, pystyakseli ${yLabel}` : ""}`}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const n = nearest(e.clientX - r.left, e.clientY - r.top);
          setHover(n ? { d: n.d, px: n.px, py: n.py } : null);
        }}
        onMouseLeave={() => setHover(null)}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const n = nearest(e.clientX - r.left, e.clientY - r.top);
          if (n && onSelect) onSelect(n.d.id);
        }}
      />
      {xLabel && <div className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 font-mono text-[10px] tracking-wider text-faint uppercase">{xLabel} →</div>}
      {yLabel && (
        <div className="pointer-events-none absolute top-1/2 left-2 origin-left -translate-y-1/2 -rotate-90 font-mono text-[10px] tracking-wider whitespace-nowrap text-faint uppercase" style={{ transform: "translate(0.6rem, 50%) rotate(-90deg)" }}>
          {yLabel} →
        </div>
      )}
      {hover && (
        <div className="pointer-events-none absolute z-10 rounded-lg border border-line-strong bg-midnight/95 px-3 py-2 text-xs shadow-xl" style={{ left: Math.min(hover.px + 12, width - 200), top: Math.max(4, hover.py - 52) }}>
          <div className="font-medium text-ink">{hover.d.label}</div>
          {hover.d.sublabel && <div className="text-muted">{hover.d.sublabel}</div>}
          <div className="mt-0.5 text-muted">{hover.d.intensity === null ? "Ei arvioitu" : `Resonanssi ${hover.d.intensity.toFixed(1)} / 10`}</div>
        </div>
      )}
      {/* accessible list for keyboard/screen-reader users */}
      {onSelect && (
        <ul className="sr-only">
          {data.map((d) => (
            <li key={d.id}>
              <button onClick={() => onSelect(d.id)}>{d.label}</button>
            </li>
          ))}
        </ul>
      )}
      {caption && <figcaption className="mt-2 text-2xs text-faint">{caption}</figcaption>}
    </figure>
  );
}
