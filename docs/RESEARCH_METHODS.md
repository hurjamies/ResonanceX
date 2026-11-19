# Research methods

ResonanceX aims to be ambitious without becoming pseudoscientific. Every value shown in the UI
belongs to exactly one of five categories, and each category has its own badge:

| Category (UI badge) | Meaning | Examples |
| --- | --- | --- |
| **Mitattu** (measured) | Deterministic signal measurement | spectrum, band energy ratios, RMS, LUFS, crest factor, stereo width, onset density |
| **Algoritminen arvio** (estimated) | Algorithmic estimate with uncertainty | BPM and tempo candidates, beats, key/mode, chords, syncopation, swing, structure, energy-arc type |
| **Mallin ennuste** (model) | ML classification hypothesis | *none in v1*: no genre, mood or instrument model is used |
| **Oma kokemus** (self-reported) | The user's report, not a physiological measurement | ratings, bodily responses, reflections, markers, comparisons |
| **Tilastollinen yhteys** (statistical) | Association in the user's own data, not causation | Spearman ρ, consistency, marker percentiles |
| **Tulkinta / hypoteesi** (interpretive) | Creative or interpretive hypothesis | open questions, Unknown Territory hypotheses, heuristic genre suggestions |

We never claim to identify a soul, unconscious motives, trauma or a mental state. The Resonance Field is a
declared feature-space map. It is not a map of consciousness.

## SonicDNA signal analysis (`sonicdna-1.0.0`)

Audio is decoded with FFmpeg to 22 050 Hz stereo float32. The STFT uses n_fft 2048 and hop 512 (≈ 23 ms).

**Rhythm.** The onset-strength envelope is median-aggregated across frequency (librosa). Its global
autocorrelation is searched over 40–220 BPM, giving *tempo candidates* with parabolic lag interpolation;
*pulse clarity* is the strongest normalised peak. Beat positions come from dynamic-programming beat tracking,
and the reported tempo is refined by the nearest autocorrelation candidate. **Tempo ambiguity**: a periodic
signal has autocorrelation peaks at every multiple of the beat period, so a slower reading (½, ⅔) is flagged
only when its peak is ≥ 1.15× the reported one, and a faster reading (2×, 1.5×) when it is ≥ 0.6×. Ambiguity
lowers the confidence and is shown in the UI. *Regularity* is exp(−CV/0.06) of the inter-beat intervals,
after removing the variance caused by frame quantisation (Δ²/6). *Local tempo* uses 8 s windows, folded to
the global tempo octave. *Syncopation* and *swing* are coarse sub-beat-grid estimates, explicitly marked
as low-reliability. *Rhythmic repetition* is the cosine similarity of consecutive 4-beat onset patterns,
which assumes a 4/4 bar.

**Spectrum.** Centroid, 85 % rolloff, flatness, bandwidth and 7-band contrast. Energy ratios are computed for
sub-bass 20–60, bass 60–250, low-mid 250–500, mid 500–4000 and treble 4000–11 025 Hz. The *bass-modulation
pulse* is the Welch spectrum (0.5–10 Hz) of the sub+bass energy envelope: its peak rate, its log
peak-to-median strength, and its rate relative to tempo (1 = the bass pulses on every beat). This is the
physical spectrum of the recording. Vibration felt in the body depends on playback equipment, level, the
room and physiology, which are not measured.

**Tonality.** HPSS is applied first, then CQT chroma from C2 upward on the harmonic component, so sustained
sub-bass kick tails don't bias the pitch classes. Key and mode come from Krumhansl–Kessler profile
correlation, with the top 4 candidates shown. *Key confidence* combines the margin over the runner-up and
the absolute correlation. Relative major and minor are often confused, and the UI says so. Chords come from
beat-synchronous (or 0.5 s block) chroma matched to 24 major/minor triad templates, with "N" for weak frames
and light smoothing; this is approximate. *Harmonic stability* is the mean cosine similarity of consecutive
beat chroma. *Tonal-tension proxy* = 1 − correlation of 6 s local chroma with the global key profile.

**Dynamics.** ITU-R BS.1770 integrated loudness (pyloudnorm, on the 22 kHz copy, so approximate). Short-term
loudness uses 3 s windows; the loudness range is the 95th minus 10th percentile after absolute and relative
gating (EBU-style). Also measured: crest factor, peak and RMS dBFS, silence fraction (< −55 dBFS), HPSS
energy ratio, stereo width (side/mid RMS) and inter-channel correlation. *Texture density* is the share of 64
mel bands within 30 dB of each frame's loudest band.

**Structure.** A self-similarity matrix of beat-synchronous MFCC + chroma + RMS, with Foote checkerboard
novelty (≈ 8 s kernel), peak-picking (≥ 8 s apart, no boundaries in the first and last 4 s), repetition letters
by segment-mean correlation (> 0.75), and **heuristic** role labels (intro, build, drop, breakdown, climax,
outro) from relative energy and slope. The energy arc uses 5 s smoothed RMS: peak position, build
gradualness (Spearman of time vs energy before the peak), longest crescendo (≥ 6 dB rise without a 1.5 dB
fall), and sudden rises (> 6 dB within 1 s).

Validated on synthetic signals (`tests/test_audio_engine.py`): tempo within ±3 %, correct key and mode,
expected chords, 1 kHz centroid within 60 Hz, band ratios, a 20 dB LUFS difference for a 10× amplitude
change, the 3.01 dB crest factor of a sine, and crescendo detection.

## Resonance Core (`core-1.0.0`)

**Resonance score** is the mean of the available *affect* ratings: bodily resonance, emotional intensity,
immersion and personal significance. It is kept separate from *preference* (enjoyment). The UI warns when
the two diverge.

**Groups.** *Strongest responses* is the top third by resonance score (minimum 2 tracks, score ≥ 5).
*Weaker responses* is the bottom third (≤ 5). *Disliked* means preference ≤ 3.

**Evidence levels** (computed, never assigned by an LLM):

| Level | Association rule (Spearman ρ, permutation test, BH-FDR, bootstrap CI) |
| --- | --- |
| Havainto (observation) | n ≥ 4 and \|ρ\| ≥ 0.6 |
| Alustava hypoteesi (preliminary) | n ≥ 5, \|ρ\| ≥ 0.5, permutation p < 0.1 |
| Toistuvasti tuettu (supported) | n ≥ 8, \|ρ\| ≥ 0.5, FDR q < 0.1 across *all* tests, 95 % bootstrap CI excludes 0 |

Other analyses:

* **Consistency.** "X of your Y strongest tracks fall in range R." The tolerance is 20 % of the library's
  p10–p90 spread (tempo ±8 BPM). A finding is reported only if it is ≥ 30 percentage points more common
  than among the rest. Tracks outside the range are listed as contradictions.
* **Collinearity.** Features that co-vary (|ρ| ≥ 0.8) are grouped into one insight. A hypothesis then
  states that they cannot yet be separated, and active learning proposes a library pair that is similar in
  one feature but different in the other (robust z-scores), or asks for such a track to be added.
* **Markers.** For each positive marker, its percentile is taken within *that track's own* distribution of
  energy, 8 s energy change, bass and brightness (chance = 50th), with a binomial sign test. Proximity to a
  structural boundary is compared with the fraction of track time that is near a boundary.
* **Pairwise.** A sign test on the feature differences between the "stronger" and "weaker" track.
  Enjoyment agreement is reported separately.
* **Negative examples.** Features where ≥ ⅔ of disliked tracks deviate by |z| ≥ 0.8. These feed the
  prompt Exclude field and are labelled as such.
* **Similarity.** RMS distance over robust z-scores of all profile features (cross-genre). Shared
  *distinctive* features are listed to explain each match.
* **Field.** PCA over robust z-scores, with explained variance and top loadings shown.

Correlation is never presented as causation. With many tests on small data, chance findings are
inevitable, which is why the evidence levels and the FDR correction exist. Only tracks analysed with the
current algorithm version are included.

## Prompt translation

Numbers are translated into followable descriptions, e.g. 88 BPM with clarity ≥ 0.6 and repetition ≥ 0.85
becomes "slow hypnotic pulse around 88 BPM". Bass pulse at 1× tempo becomes "pulsing bassline locked to
every beat". A feature is "high" or "low" relative to the user's library (p25/p75 once n ≥ 5), otherwise
relative to broad absolute ranges. Values come from: selected sources (measured), profile targets (when
their evidence is ≥ preliminary, they override sources), explicit user controls, or **objective
conventions**. The last are general musical conventions for an objective such as melancholy; they are
labelled as such and kept separate from **personal associations** drawn from the user's own ratings of that
dimension. Genre suggestions are rule-based heuristics, labelled as such; there is no genre classifier.

## Feedback loop

Objective alignment is the share of target features measured within tolerance (tempo also accepts ½× and 2×
metrical equivalents), plus the energy-arc type. Subjective resonance comes from the user's rating of the
generated track. The verdict (*supports / challenges / surprise / inconclusive / mixed*) is a simple,
transparent rule; it doesn't claim causality. Generated tracks enter the profile as ordinary experiences.
