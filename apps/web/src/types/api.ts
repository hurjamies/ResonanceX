export type EvidenceLevel = "insufficient" | "observation" | "preliminary" | "supported";
export type AssetStatus = "pending" | "processing" | "completed" | "failed";

export interface Job {
  id: number;
  status: "queued" | "processing" | "completed" | "failed";
  stage: string | null;
  stages_done: number;
  stages_total: number;
  error: string | null;
}

export interface Asset {
  id: number;
  kind: string;
  origin: "library" | "generated";
  original_filename: string;
  sha256: string;
  size_bytes: number;
  mime_type: string | null;
  codec: string | null;
  container_format: string | null;
  duration_seconds: number | null;
  sample_rate: number | null;
  channels: number | null;
  bit_rate: number | null;
  title: string | null;
  artist: string | null;
  album: string | null;
  genre_tag: string | null;
  rights_confirmed: boolean;
  prompt_id: number | null;
  source_provider: string | null;
  status: AssetStatus;
  status_stage: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  audio_url: string;
  job: Job | null;
  rated: boolean;
  rating_summary: Record<string, number> | null;
  marker_count: number;
  metadata_tags?: Record<string, string>;
  prompt?: { id: number; title: string; mode: string } | null;
}

export interface UploadResult {
  filename: string;
  ok: boolean;
  duplicate?: boolean;
  error?: string;
  code?: string;
  asset?: Asset;
}

export interface Segment {
  index: number;
  start: number;
  end: number;
  energy_db: number;
  relative_energy_db: number;
  energy_slope_db_per_s: number;
  bass_ratio: number | null;
  brightness_hz: number | null;
  boundary_strength: number | null;
  letter: string;
  repeated: boolean;
  role: string;
  label_confidence: string;
}

export interface AnalysisSummary {
  algorithm_version: string;
  duration_seconds: number;
  rhythm: {
    tempo_bpm: number | null;
    tempo_confidence: number | null;
    tempo_candidates: { bpm: number; strength: number }[];
    tempo_ambiguity: { kind: string; alternative_bpm: number; relative_strength: number } | null;
    tempo_variation_bpm: number | null;
    beat_count: number;
    rhythmic_regularity: number | null;
    pulse_clarity: number | null;
    onset_density: number | null;
    beat_strength: number | null;
    syncopation: number | null;
    swing_ratio: number | null;
    swing_confidence: number | null;
    rhythmic_repetition: number | null;
  };
  spectral: {
    centroid_mean_hz: number | null;
    centroid_std_hz: number | null;
    rolloff_mean_hz: number | null;
    flatness_mean: number | null;
    bandwidth_mean_hz: number | null;
    contrast_mean: (number | null)[];
    band_energy_ratio: Record<string, number | null>;
    bass_modulation: { rate_hz: number | null; strength: number | null; depth: number | null; beat_relation: number | null };
    bands_hz: Record<string, [number, number]>;
  };
  tonality: {
    key: string;
    mode: "major" | "minor";
    key_label: string;
    key_confidence: number | null;
    key_candidates: { key: string; mode: string; correlation: number }[];
    pitch_class_distribution: number[];
    harmonic_stability: number | null;
    chord_change_rate_per_min: number | null;
    chord_vocabulary_size: number;
    harmonic_repetition: number | null;
    tonal_tension_mean: number | null;
    chords: { start: number; end: number; label: string }[];
    chord_method: string;
  };
  dynamics: {
    integrated_loudness_lufs: number | null;
    loudness_range_lu: number | null;
    short_term_loudness_std: number | null;
    peak_dbfs: number | null;
    rms_dbfs: number | null;
    crest_factor_db: number | null;
    silence_fraction: number | null;
    harmonic_percussive_ratio: number | null;
    percussive_fraction: number | null;
    stereo_width: number | null;
    stereo_correlation: number | null;
    texture_density: number | null;
    loudness_note: string;
  };
  structure: {
    segment_count: number;
    boundaries: number[];
    energy_arc: {
      type: string;
      peak_position: number | null;
      build_gradualness: number | null;
      crescendo_seconds: number | null;
      sudden_changes: number;
      sudden_changes_per_min: number | null;
      energy_std_db: number | null;
    };
    peak_moments: { time: number; kind: string; value_db: number }[];
    structural_repetition: number | null;
    method: string;
  };
  features: Record<string, number | null>;
}

export interface Analysis {
  id: number;
  asset_id: number;
  algorithm_version: string;
  current_version: string;
  outdated: boolean;
  created_at: string;
  analysis_seconds: number;
  summary: AnalysisSummary;
  segments: Segment[];
}

export type Series = (number | null)[];
export interface TimeSeries {
  duration: number;
  dt: number;
  rms_db: Series;
  energy_env_db: Series;
  centroid_hz: Series;
  flatness: Series;
  onset_strength: Series;
  bands: Record<string, Series>;
  local_tempo: Series;
  local_tempo_dt: number;
  short_term_loudness: { t: Series; v: Series };
  tension: { t: Series; v: Series };
  novelty: { t: Series; v: Series };
  chroma: { dt: number; values: Series[] };
  beats: number[];
  onsets: number[];
  waveform: { buckets: number; min: number[]; max: number[] };
}

export interface Rating {
  asset_id: number;
  dimensions: Record<string, number | null>;
  body_responses: string[];
  reflections: Record<string, string>;
  context: Record<string, string | null>;
  updated_at: string | null;
  exists: boolean;
}

export interface Marker {
  id: number;
  asset_id: number;
  start_seconds: number;
  end_seconds: number | null;
  label: string;
  intensity: number | null;
  note: string | null;
  created_at: string;
}

export interface Comparison {
  id: number;
  asset_a_id: number;
  asset_b_id: number;
  stronger: "a" | "b" | "equal" | null;
  enjoyed: "a" | "b" | "equal" | null;
  note: string | null;
  created_at: string;
}

export interface FeatureDef {
  key: string;
  label: string;
  unit: string;
  category: "measured" | "estimated";
  group: string;
  low_fi: string;
  high_fi: string;
  in_profile: boolean;
  log_scale: boolean;
}

export interface Vocabulary {
  dimensions: { key: string; label: string; hint: string }[];
  body_responses: { key: string; label: string }[];
  reflections: { key: string; label: string }[];
  context: Record<string, { key: string; label: string }[]>;
  markers: { key: string; label: string }[];
  features: FeatureDef[];
  segment_roles: Record<string, string>;
  energy_arcs: Record<string, string>;
  evidence_levels: Record<EvidenceLevel, string>;
  analysis_stages: string[];
  allowed_extensions: string[];
}

export interface TrackRef {
  asset_id: number;
  title: string | null;
  artist: string | null;
  origin: string;
  resonance_score: number | null;
  preference: number | null;
  value?: number | null;
  value_label?: string;
  rating?: number;
  role?: string;
}

export interface Insight {
  id: string;
  kind: string;
  feature?: string;
  dimension?: string;
  title: string;
  explanation: string;
  evidence_level: EvidenceLevel;
  evidence_level_label: string;
  evidence: Record<string, unknown>;
  supporting_tracks: TrackRef[];
  contrasting_tracks: TrackRef[];
  timestamps: { asset_id: number; title: string; time: number; label: string }[];
  suggested_experiment: string;
  generated_at: string;
  core_version: string;
  analysis_version: string;
}

export interface TargetFeature {
  feature: string;
  label: string;
  median: number;
  p25: number;
  p75: number;
  library_median: number;
  z: number;
  direction: "high" | "low" | "typical";
  evidence_level: EvidenceLevel;
  rho: number | null;
  n: number;
  value_label: string;
}

export interface Association {
  dimension: string;
  dimension_label: string;
  feature: string;
  feature_label: string;
  rho: number;
  n: number;
  p_permutation: number;
  q_fdr: number;
  ci_low: number | null;
  ci_high: number | null;
  evidence_level: EvidenceLevel;
  tests_total: number;
}

export interface FieldPoint {
  asset_id: number;
  title: string | null;
  artist: string | null;
  origin: string;
  features: Record<string, number | null>;
  ratings: Record<string, number | null>;
  resonance_score: number | null;
  pca: [number, number] | null;
  body_responses: string[];
  markers: number;
}

export interface SuggestedExperiment {
  kind: "pairwise" | "rate" | "marker" | "upload";
  title: string;
  description: string;
  asset_ids: number[];
  hypothesis_id?: string;
}

export interface Profile {
  version: number;
  snapshot_created_at: string | null;
  core_version: string;
  analysis_version: string;
  generated_at: string;
  data_stage: "empty" | "collecting" | "preliminary" | "developing";
  counts: {
    tracks_analyzed: number;
    tracks_rated: number;
    generated_tracks: number;
    markers: number;
    comparisons: number;
    ratings_by_dimension: Record<string, number>;
    body_responses: Record<string, number>;
  };
  group_definition: { basis: string; description: string; top: number[]; bottom: number[]; disliked: number[]; affect_dimensions: string[] };
  library_stats: Record<string, { n: number; median: number; p10: number; p25: number; p75: number; p90: number; min: number; max: number }>;
  targets: { basis: "none" | "strongest_responses"; group_basis: string; tracks: TrackRef[]; features: TargetFeature[] };
  summary_lines: { feature: string; text: string; evidence_level: EvidenceLevel }[];
  associations: Association[];
  associations_tested: number;
  insights: Insight[];
  contradictions: { insight_id: string; feature: string; track: TrackRef; note: string }[];
  marker_analysis: { n_markers: number; n_tracks: number; findings: { title: string; explanation: string; evidence_level: EvidenceLevel }[] };
  pairwise: { n: number; n_stronger: number; n_enjoyed: number; agreement: number | null; features: unknown[] };
  hypotheses: { id: string; statement: string; status: string; basis: Record<string, unknown> }[];
  suggested_experiments: SuggestedExperiment[];
  field: { points: FieldPoint[]; pca: { explained_variance: number[]; loadings: { feature: string; label: string; weight: number }[][] } | null; method: string };
}

export interface SimilarTrack extends TrackRef {
  distance: number;
  shared_features: { feature: string; label: string; phrase: string }[];
  genre_tag: string | null;
}

export interface SunoPackage {
  mode: "deep_resonance" | "intensification" | "unknown_territory";
  mode_label: string;
  objective: string | null;
  objective_label: string | null;
  title: string;
  primary_genre: string | null;
  hybrid_genre: string | null;
  style: string;
  style_dropped: string[];
  lyrics: string;
  lyrics_note_fi: string;
  instrumental: boolean;
  vocal: string;
  exclude: string;
  creative_direction: string;
  evidence_fi: string[];
  uncertainty_fi: string[];
  experimental_hypotheses: string[];
  target_summary: { feature: string; label: string; target: number; tolerance: number; unit: string; source: string; evidence_level: string }[];
  tempo_hint: number | null;
  settings: { model: string; weirdness: number; style_influence: number; variety: number; note_fi: string };
  field_support: Record<string, { kind: "suno_field" | "free_text_hint" | "imperfect"; note_fi: string }>;
  suno_url: string;
}

export interface PromptRecord {
  id: number;
  batch_id: string;
  parent_id: number | null;
  mode: SunoPackage["mode"];
  objective: string | null;
  profile_version: number | null;
  provider: string;
  provider_model: string | null;
  source_asset_ids: number[];
  controls: Record<string, unknown>;
  specification: Record<string, unknown> & { target_features: { feature: string; label: string; target: number; tolerance: number }[] };
  compiled: SunoPackage;
  edited: Partial<SunoPackage>;
  effective: SunoPackage;
  saved: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  generated_assets?: { id: number; title: string | null; status: string }[];
}

export interface PromptOptions {
  objectives: { key: string; label: string; dimension: string }[];
  providers: Provider[];
  vocal_options: { key: string; label: string }[];
}

export interface Provider {
  id: string;
  name: string;
  kind: "manual" | "assisted" | "api";
  configured: boolean | null;
  status: "available" | "external" | "not_configured" | "configured" | "verified";
  status_fi: string;
  generation: boolean;
  models?: { id: string; label: string; note_fi: string }[];
  default_model?: string;
  cost?: { usd_per_minute: number; max_per_request_usd: number; basis_fi: string };
  setup_fi: string[];
  notes_fi: string;
  docs: string[];
  last_success_at?: string | null;
}

export interface CostEstimate {
  currency: string;
  amount: number;
  minutes: number;
  rate_per_minute: number;
  basis: string;
  basis_fi: string;
  exceeds_cap: boolean;
  cap: number;
  note_fi: string;
}

export interface GenerationJob {
  id: number;
  provider: string;
  prompt_id: number;
  prompt_title?: string | null;
  status: "awaiting_confirmation" | "queued" | "running" | "completed" | "failed" | "cancelled";
  provider_model: string | null;
  request: { endpoint: string; mode: "prompt" | "plan"; query: Record<string, string>; body: Record<string, unknown> };
  disclosure: string[];
  cost_estimate: CostEstimate;
  confirmed_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  result_asset_id: number | null;
  result_asset?: { id: number; title: string | null; status: string } | null;
  response_meta: Record<string, unknown> & { warnings?: string[]; plan_created_at?: string; requeued_note?: string };
  error: string | null;
  created_at: string;
}

export interface Handoff {
  prompt_id: number;
  markdown: string;
  import_command: string;
  slash_command: string;
}

export interface AlignmentRow {
  feature: string;
  label: string;
  target: number;
  tolerance: number;
  measured: number | null;
  target_label: string;
  measured_label: string;
  delta?: number;
  status: "match" | "near" | "miss" | "metrical_equivalent" | "unmeasured";
  source: string;
  note: string | null;
}

export interface Experiment {
  id: number;
  prompt: { id: number; title: string; mode: string; mode_label: string; objective: string | null; profile_version: number | null; created_at: string; hypotheses: string[] } | null;
  asset: { id: number; title: string | null; status: string; duration_seconds: number | null } | null;
  alignment: { features: AlignmentRow[]; energy_arc: { target: string; measured: string; status: string } | null; matches: number; near: number; total: number; score: number | null };
  outcome: {
    resonance_score: number | null;
    preference: number | null;
    library_mean_resonance: number | null;
    alignment_score: number | null;
    verdict: string | null;
    verdict_fi: string;
    deviations: { feature: string; label: string; delta: number | null }[];
    rated: boolean;
  };
  outcome_note: string | null;
  created_at: string;
}

export interface Overview {
  counts: Profile["counts"] & { assets_total: number; prompts: number; experiments: number };
  profile_version: number;
  data_stage: Profile["data_stage"];
  summary_lines: Profile["summary_lines"];
  insights: Insight[];
  recent_prompts: { id: number; title: string; mode: string; mode_label: string; created_at: string; style: string }[];
  recent_experiments: { id: number; prompt_id: number; asset_id: number; score: number | null }[];
  incomplete: { id: number; title: string; status: string; stage: string | null; error: string | null }[];
  next_action: { kind: string; title: string; description: string; href: string };
}

export interface SettingsInfo {
  data_dir: string;
  database: string;
  uploads_bytes: number;
  analysis_bytes: number;
  max_upload_mb: number;
  max_duration_seconds: number;
  analysis_version: string;
  core_version: string;
  ffmpeg: boolean;
  bind_host: string;
  llm: { configured: boolean; status_fi: string };
}
