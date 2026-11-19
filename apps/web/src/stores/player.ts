import { create } from "zustand";

/**
 * One global <audio> element for the whole app. Components that need a
 * frame-accurate playhead read `getAudioTime()` inside requestAnimationFrame
 * instead of subscribing to React state (keeps rendering cheap).
 */
let audio: HTMLAudioElement | null = null;

export function getAudio(): HTMLAudioElement {
  if (!audio) {
    audio = new Audio();
    audio.preload = "metadata";
    const set = usePlayer.setState;
    let last = 0;
    audio.addEventListener("timeupdate", () => {
      const t = audio!.currentTime;
      if (Math.abs(t - last) > 0.2) {
        last = t;
        set({ currentTime: t });
      }
    });
    audio.addEventListener("play", () => set({ playing: true }));
    audio.addEventListener("pause", () => set({ playing: false, currentTime: audio!.currentTime }));
    audio.addEventListener("ended", () => set({ playing: false }));
    audio.addEventListener("loadedmetadata", () => {
      const d = audio!.duration;
      if (Number.isFinite(d)) set({ duration: d });
    });
    audio.addEventListener("error", () => set({ playing: false, error: "Toisto epäonnistui – selain ei ehkä tue tätä tiedostomuotoa." }));
  }
  return audio;
}

export const getAudioTime = () => (audio ? audio.currentTime : 0);

interface View {
  start: number;
  end: number;
}

interface PlayerState {
  assetId: number | null;
  title: string;
  artist: string | null;
  playing: boolean;
  currentTime: number;
  duration: number;
  error: string | null;
  view: View;
  selection: View | null;
  load: (a: { id: number; title: string | null; artist: string | null; audio_url: string; duration_seconds: number | null }, autoplay?: boolean) => void;
  toggle: () => void;
  seek: (t: number) => void;
  setView: (v: View) => void;
  zoom: (factor: number, center?: number) => void;
  fit: () => void;
  setSelection: (s: View | null) => void;
}

const MIN_SPAN = 2;

export const usePlayer = create<PlayerState>((set, get) => ({
  assetId: null,
  title: "",
  artist: null,
  playing: false,
  currentTime: 0,
  duration: 0,
  error: null,
  view: { start: 0, end: 1 },
  selection: null,
  load: (a, autoplay = false) => {
    const el = getAudio();
    if (get().assetId !== a.id) {
      el.src = a.audio_url;
      const d = a.duration_seconds || 0;
      set({ assetId: a.id, title: a.title || "Nimetön", artist: a.artist, currentTime: 0, duration: d, view: { start: 0, end: d || 1 }, selection: null, error: null });
    }
    if (autoplay) el.play().catch(() => set({ playing: false }));
  },
  toggle: () => {
    const el = getAudio();
    if (!get().assetId) return;
    if (el.paused) el.play().catch(() => set({ playing: false }));
    else el.pause();
  },
  seek: (t) => {
    const el = getAudio();
    const d = get().duration || el.duration || 0;
    const clamped = Math.max(0, Math.min(d || t, t));
    el.currentTime = clamped;
    set({ currentTime: clamped });
    // keep the playhead visible when zoomed
    const { view } = get();
    const span = view.end - view.start;
    if (clamped < view.start || clamped > view.end) {
      const start = Math.max(0, Math.min(d - span, clamped - span * 0.25));
      set({ view: { start, end: start + span } });
    }
  },
  setView: (v) => {
    const d = get().duration;
    let { start, end } = v;
    if (end - start < MIN_SPAN) end = start + MIN_SPAN;
    if (start < 0) {
      end -= start;
      start = 0;
    }
    if (d && end > d) {
      start = Math.max(0, start - (end - d));
      end = d;
    }
    set({ view: { start, end } });
  },
  zoom: (factor, center) => {
    const { view, currentTime } = get();
    const c = center ?? (currentTime >= view.start && currentTime <= view.end ? currentTime : (view.start + view.end) / 2);
    const span = (view.end - view.start) * factor;
    get().setView({ start: c - (c - view.start) * factor, end: c - (c - view.start) * factor + span });
  },
  fit: () => set({ view: { start: 0, end: get().duration || 1 } }),
  setSelection: (s) => set({ selection: s }),
}));
