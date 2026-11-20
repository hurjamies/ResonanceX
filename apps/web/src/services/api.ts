import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Analysis,
  Asset,
  Comparison,
  Experiment,
  GenerationJob,
  Handoff,
  Marker,
  MusicFolder,
  MusicSuggestion,
  Overview,
  Profile,
  PromptOptions,
  PromptRecord,
  Provider,
  Rating,
  SettingsInfo,
  SimilarTrack,
  TimeSeries,
  UploadResult,
  Vocabulary,
} from "@/types/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  vocabulary: () => request<Vocabulary>("/api/vocabulary"),
  assets: (params: { origin?: string } = {}) => request<Asset[]>(`/api/assets${params.origin ? `?origin=${params.origin}` : ""}`),
  asset: (id: number) => request<Asset>(`/api/assets/${id}`),
  patchAsset: (id: number, body: Partial<Pick<Asset, "title" | "artist" | "genre_tag" | "folder_id">>) => request<Asset>(`/api/assets/${id}`, { method: "PATCH", body: json(body) }),
  musicFolders: () => request<MusicFolder[]>("/api/music/folders"),
  createMusicFolder: (name: string) => request<MusicFolder>("/api/music/folders", { method: "POST", body: json({ name }) }),
  renameMusicFolder: (id: number, name: string) => request<MusicFolder>(`/api/music/folders/${id}`, { method: "PATCH", body: json({ name }) }),
  deleteMusicFolder: (id: number) => request<{ deleted: number; unfiled_tracks: number }>(`/api/music/folders/${id}`, { method: "DELETE" }),
  folderPrompt: (id: number) => request<{ batch_id: string; prompt: PromptRecord }>(`/api/music/folders/${id}/prompt`, { method: "POST" }),
  musicSuggestion: () => request<MusicSuggestion>("/api/music/suggestion"),
  suggestionPrompt: () => request<{ batch_id: string; prompt: PromptRecord }>("/api/music/suggestion/prompt", { method: "POST" }),
  deleteAsset: (id: number) => request<{ deleted: number }>(`/api/assets/${id}`, { method: "DELETE" }),
  reanalyze: (id: number) => request<{ queued: boolean }>(`/api/assets/${id}/reanalyze`, { method: "POST" }),
  upload: (files: File[], opts: { rights: boolean; promptId?: number; folderId?: number }) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("rights_confirmed", String(opts.rights));
    if (opts.promptId) fd.append("prompt_id", String(opts.promptId));
    if (opts.folderId) fd.append("folder_id", String(opts.folderId));
    return request<{ results: UploadResult[] }>("/api/assets/upload", { method: "POST", body: fd });
  },
  analysis: (id: number) => request<Analysis>(`/api/assets/${id}/analysis`),
  timeseries: (id: number) => request<TimeSeries>(`/api/assets/${id}/timeseries`),
  similar: (id: number) => request<SimilarTrack[]>(`/api/assets/${id}/similar`),
  rating: (id: number) => request<Rating>(`/api/assets/${id}/rating`),
  putRating: (id: number, body: Omit<Rating, "asset_id" | "updated_at" | "exists">) => request<Rating>(`/api/assets/${id}/rating`, { method: "PUT", body: json(body) }),
  markers: (id: number) => request<Marker[]>(`/api/assets/${id}/markers`),
  createMarker: (id: number, body: Omit<Marker, "id" | "asset_id" | "created_at">) => request<Marker>(`/api/assets/${id}/markers`, { method: "POST", body: json(body) }),
  updateMarker: (mid: number, body: Omit<Marker, "id" | "asset_id" | "created_at">) => request<Marker>(`/api/markers/${mid}`, { method: "PUT", body: json(body) }),
  deleteMarker: (mid: number) => request<{ deleted: number }>(`/api/markers/${mid}`, { method: "DELETE" }),
  comparisons: () => request<Comparison[]>("/api/comparisons"),
  createComparison: (body: Omit<Comparison, "id" | "created_at"> & { suggested_by_core?: boolean }) => request<Comparison>("/api/comparisons", { method: "POST", body: json(body) }),
  deleteComparison: (id: number) => request<{ deleted: number }>(`/api/comparisons/${id}`, { method: "DELETE" }),
  profile: () => request<Profile>("/api/profile"),
  profileHistory: () => request<{ version: number; created_at: string; tracks_rated: number; tracks_analyzed: number; insights: number; summary_lines: Profile["summary_lines"] }[]>("/api/profile/history"),
  overview: () => request<Overview>("/api/overview"),
  promptOptions: () => request<PromptOptions>("/api/prompt-options"),
  generatePrompts: (body: { source_asset_ids: number[]; objective: string | null; controls: Record<string, unknown> }) =>
    request<{ batch_id: string; profile_version: number; prompts: PromptRecord[] }>("/api/prompts/generate", { method: "POST", body: json(body) }),
  prompts: (batchId?: string) => request<PromptRecord[]>(`/api/prompts${batchId ? `?batch_id=${encodeURIComponent(batchId)}` : ""}`),
  prompt: (id: number) => request<PromptRecord>(`/api/prompts/${id}`),
  patchPrompt: (id: number, body: { edited?: Record<string, unknown>; saved?: boolean; notes?: string }) => request<PromptRecord>(`/api/prompts/${id}`, { method: "PATCH", body: json(body) }),
  duplicatePrompt: (id: number) => request<PromptRecord>(`/api/prompts/${id}/duplicate`, { method: "POST" }),
  deletePrompt: (id: number) => request<{ deleted: number }>(`/api/prompts/${id}`, { method: "DELETE" }),
  experiments: () => request<Experiment[]>("/api/experiments"),
  patchExperiment: (id: number, body: { outcome_note: string }) => request<Experiment>(`/api/experiments/${id}`, { method: "PATCH", body: json(body) }),
  providers: () => request<Provider[]>("/api/providers"),
  handoff: (promptId: number) => request<Handoff>(`/api/prompts/${promptId}/handoff`),
  generations: (promptId?: number) => request<GenerationJob[]>(`/api/generations${promptId ? `?prompt_id=${promptId}` : ""}`),
  generation: (id: number) => request<GenerationJob>(`/api/generations/${id}`),
  prepareGeneration: (body: { prompt_id: number; provider: "elevenlabs"; model_id?: string; duration_seconds?: number }) =>
    request<GenerationJob>("/api/generations", { method: "POST", body: json(body) }),
  planGeneration: (id: number, acceptDisclosure: boolean) => request<GenerationJob>(`/api/generations/${id}/plan`, { method: "POST", body: json({ accept_disclosure: acceptDisclosure }) }),
  confirmGeneration: (id: number, acceptedCost: number, acceptDisclosure: boolean) =>
    request<GenerationJob>(`/api/generations/${id}/confirm`, { method: "POST", body: json({ accepted_cost: acceptedCost, accept_disclosure: acceptDisclosure }) }),
  cancelGeneration: (id: number) => request<GenerationJob>(`/api/generations/${id}/cancel`, { method: "POST" }),
  settings: () => request<SettingsInfo>("/api/settings"),
};

// ------------------------------------------------------------------ hooks
export const qk = {
  vocab: ["vocabulary"],
  assets: ["assets"],
  musicFolders: ["music-folders"],
  musicSuggestion: ["music-suggestion"],
  asset: (id: number) => ["asset", id],
  analysis: (id: number) => ["analysis", id],
  ts: (id: number) => ["timeseries", id],
  rating: (id: number) => ["rating", id],
  markers: (id: number) => ["markers", id],
  similar: (id: number) => ["similar", id],
  profile: ["profile"],
  overview: ["overview"],
  prompts: ["prompts"],
  experiments: ["experiments"],
  comparisons: ["comparisons"],
  providers: ["providers"],
  generations: ["generations"],
};

export function useProviders() {
  return useQuery({ queryKey: qk.providers, queryFn: api.providers });
}

export function useVocabulary() {
  return useQuery({ queryKey: qk.vocab, queryFn: api.vocabulary, staleTime: Infinity });
}

export function useAssets() {
  return useQuery({
    queryKey: qk.assets,
    queryFn: () => api.assets(),
    refetchInterval: (q) => (q.state.data?.some((a) => a.status === "pending" || a.status === "processing") ? 1500 : false),
  });
}

export function useMusicFolders() {
  return useQuery({ queryKey: qk.musicFolders, queryFn: api.musicFolders, refetchInterval: (q) => q.state.data?.some((f) => f.pending_count > 0) ? 2000 : false });
}

export function useAsset(id: number) {
  return useQuery({
    queryKey: qk.asset(id),
    queryFn: () => api.asset(id),
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "pending" || q.state.data.status === "processing") ? 1200 : false),
  });
}

export function useProfile() {
  return useQuery({ queryKey: qk.profile, queryFn: api.profile });
}

/** Invalidate everything derived from experiences (profile, overview, experiments). */
export function useInvalidateDerived() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: qk.profile });
    qc.invalidateQueries({ queryKey: qk.overview });
    qc.invalidateQueries({ queryKey: qk.experiments });
    qc.invalidateQueries({ queryKey: qk.assets });
    qc.invalidateQueries({ queryKey: qk.musicFolders });
    qc.invalidateQueries({ queryKey: qk.musicSuggestion });
  };
}

export function useUpload() {
  const qc = useQueryClient();
  const inv = useInvalidateDerived();
  return useMutation({
    mutationFn: ({ files, rights, promptId, folderId }: { files: File[]; rights: boolean; promptId?: number; folderId?: number }) => api.upload(files, { rights, promptId, folderId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.assets });
      qc.invalidateQueries({ queryKey: qk.prompts });
      inv();
    },
  });
}
