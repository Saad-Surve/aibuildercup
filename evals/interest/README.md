# Predicted audience interest

Measured on 13 October 2026, retrained on 14 October with 87 creator videos (was 46). The review heatmap only marks moments a reviewer flagged, so
most of a good video has no colour. The interest lane fills every five-second bin with a
**relative** estimate of where viewers lean in or drift, learned from YouTube's public
"Most Replayed" graph, and marks the stretches that most beat or fall short of the typical
drop-off for that point in a video.

**Headline.** On creator channels the model never trained on, the predicted deviations from
the typical drop-off correlate with the real ones at **ρ = 0.15 (95% CI 0.10–0.20)**.
Predicted dips land in the true bottom quarter **35%** of the time and peaks in the true top
quarter **35%**, against 25% by chance. Most of that comes from Gemini's per-moment
signals. Transcript statistics alone (pace, pauses, fillers) are only barely above chance
(ρ = 0.07 [0.03, 0.12]).

## What the label is, and is not

The label is YouTube's Most Replayed graph: replay intensity per segment, normalised to 0–1
**within each video**. It is a public proxy for where viewers rewatch or seek, available for
videos with enough views. It is **not retention**, watch time or a cross-video score. The
model ranks moments inside one video. The UI never shows a percentage, and the info panel
says so.

## Data

| Source | Videos | Channels | Median length | Role |
|---|---:|---:|---:|---|
| Creator set (collected) | 87 | 81 | 11.9 min | Grouped cross-validation over channels, then training |
| [Content Behavior Corpus](https://huggingface.co/datasets/behavior-in-the-wild/content-behavior-corpus) (Adobe, MIT) | 9,775 | 2,106 | 70 s | Training data, plus a short-form held-out check |

- **Creator set.** YouTube searches across finance, careers, fitness, tech, cooking, study and
  Hindi-language niches, filtered to 4–25 minutes, ≥100k views and a Most Replayed graph,
  and capped at three videos per channel. Metadata and the graph come from yt-dlp. Transcripts
  are YouTube's original-language ASR track (transcript API), or local Whisper
  (`large-v3-turbo` on Apple silicon) when YouTube blocked caption requests. Whisper downloads
  audio only, and the audio is deleted after transcription. The split is 60 English, 26
  Hindi or Hinglish and 1 Telugu video. Raw files stay in the gitignored `raw/` folder. Only video IDs
  ([videos.csv](videos.csv)) and derived results are committed.
- **Corpus.** Short brand-channel videos with Whisper transcripts and replay markers. Only
  speech-led clips are kept: at least 30 s, at least 80 wpm and at least 10 markers.
- **Gemini signals** were computed for every creator video and for a seeded 234-clip corpus
  sample. Gemini returned 429s at higher sample sizes. The pass cost about $0.011 per
  long-form video and well under $0.01 per clip at the configured Flash-Lite rates.

Training and inference share one implementation, `app/services/interest.py`. Production
stores segment timings, not word timings, so every training transcript is re-segmented with
the production segmenter and words are spread over segments exactly as at inference.

## Features and model

- **Position:** relative position, its square, opening and closing terms, and their
  interaction with log video length. Together these form the "typical drop-off" head.
- **Transcript:** speech density, words per minute, longest pause, filler rate, questions,
  numbers, direct address, lexical novelty and pace change. Each comes with a ±2-bin
  rolling mean and a within-video version (value minus the video's own mean).
- **Gemini signals** (`gemini-3.1-flash-lite`, one call per ten minutes, at most four per
  video): each bin is rated 1–5 for hook, payoff, novelty, open loop, emotion, humour,
  practical value, on-screen cue and tangent, returned as a compact 9-digit code.
- **Model:** weighted ridge regression on standardised features, shipped as JSON
  coefficients (`app/assets/interest/model.json`, 9 KB), so the API needs no ML runtime.
  Labels are z-scored within each video.
- **Lift** is the prediction minus the position head. Peaks and dips are chosen on lift, so a
  dip is content that underperforms its place in the video, not just the end of every video.

The largest content weights in the shipped head are practical value, hook, payoff and humour
(each relative to the rest of the video, so positive), and the longest-pause context (negative).

## Results

Grouped five-fold cross-validation over **creator channels**. Each fold trains on the recipe's
data minus the held channels and tests on those channels' videos. The position baseline is
refit on the same training data in each fold. Chance precision is 0.25.

| Recipe | n | ρ | Position ρ | **Lift ρ [95% CI]** | Lift peak precision | Lift dip precision |
|---|---:|---:|---:|---|---:|---:|
| Creator, transcript (fallback) | 87 | 0.272 | 0.258 | 0.074 [0.029, 0.120] | 0.31 | 0.31 |
| Corpus + creator, transcript | 87 | 0.253 | 0.245 | 0.066 [0.029, 0.104] | 0.31 | 0.30 |
| Corpus only, transcript | 87 | 0.094 | 0.105 | −0.260 [−0.308, −0.208] | 0.16 | 0.11 |
| Creator, transcript + Gemini | 87 | 0.302 | 0.258 | 0.149 [0.099, 0.197] | 0.37 | 0.34 |
| **Corpus + creator, transcript + Gemini (shipped)** | 87 | **0.282** | 0.245 | **0.151 [0.101, 0.200]** | **0.35** | **0.35** |

Retrain of 14 October. With 46 creator videos (13 October) the shipped recipe scored lift ρ
0.172 [0.099, 0.241], peak precision 0.35 and dip precision 0.37. With 87 videos the point
estimate is slightly lower and the interval about 30% narrower, with the same lower bound. The
new videos came from a five-hour macOS collector run (`collector/run-macos.sh`) and lean towards
Hindi smartphone reviews, because that niche was being searched when YouTube blocked captions
and collection switched to Whisper. The model was rewritten because the larger test population
makes the estimate more trustworthy, not because the number went up.

Short-form check (corpus-trained, 2,981 clips on held-out corpus channels): transcript ρ 0.304
against position 0.300, lift ρ 0.053 [0.040, 0.066]. Replay curves of one-minute brand clips
are almost entirely positional.

What the evidence supports:

1. **Gemini's semantic signals carry the content effect.** Without them the lift is barely
   above zero (0.07). With them it doubles to 0.15 on unseen creators. Adding the signalled
   corpus clips no longer changes it (0.151 against 0.149 creator-only).
2. **Short-form shape does not transfer to long-form.** A position and transcript model
   trained only on the corpus is worse than chance on creator videos. It is used only
   alongside creator data, with both sources weighted equally.
3. **It is a weak, useful signal, not a verdict.** ρ ≈ 0.3 overall and 0.15 beyond position
   mean the markers point at places worth reviewing. The info panel says this in those words.

## Limits

- **Selection.** The shipped recipe was chosen as the best of five on these same CV results,
  so its numbers are mildly optimistic. 87 creator videos from 81 channels is still a small
  test population, and it is skewed towards tech and Hindi-language channels.
- **Most Replayed is a proxy.** It reflects rewatching and seeking, and it exists only for
  popular videos. A creator's own retention curve (YouTube Analytics `audienceWatchRatio`)
  would be the better label for retention prediction. Channel calibration now uses this
  label for the position baseline only (see below); it does not retrain or validate the
  content model. The live channel available for verification had insufficient data.
- **Transcript only.** The model sees no frames or audio energy. Visual moments are only
  visible when the speech points at them.
- **Fallback.** When the Gemini pass is unavailable, the transcript-only head draws the
  curve, but no peaks or dips are marked, because its lift (0.07) is too weak to point at
  moments.
- **Collection terms.** yt-dlp and the transcript API sit outside YouTube's API terms. The
  data was gathered for research evaluation, is not redistributed, and is kept to metadata,
  replay graphs and transcripts.

## Channel drop-off calibration (v1)

The interest info panel offers **Calibrate to my channel** when YouTube is connected.
It reads the owner's most recent 40 uploads through the official Data API and queries
`audienceWatchRatio` by `elapsedVideoTimeRatio` through YouTube Analytics, targeting the
explicit connected channel ID. Views and retention use the same 365-day window, ending
three days ago to allow for reporting delay. No transcripts, caption downloads, scraping,
Gemini calls or YouTube writes are involved. The optional transcript/Gemini fit check is
not implemented: caption availability and additional model calls would complicate this
baseline-only feature. No additional scopes are requested.

There are two duration buckets: up to three minutes, and longer. A bucket needs three
videos of at least 30 seconds, each with >=100 report-period views and >=90 finite retention
points covering 1–99% of elapsed time without large gaps; flat curves are excluded. Each
curve is interpolated onto 100 evenly spaced positions and z-scored within the video, to
match the generic replay model's units. The channel head is a weighted mean, with each
video weighted `min(1, views / 1000)`. Shrinkage uses ten generic video equivalents:
`channelWeight = sum(video weights) / (sum(video weights) + 10)`. A viral upload cannot
outweigh all the others; sparse data stays close to the generic head. Counts, views,
bucket weights, date, insufficiency reasons and the next allowed attempt are visible.

The provider makes at most **43 YouTube requests** (one playlist page, one metadata batch,
one views report, up to forty retention reports), with no retries and a 180-second read
budget. A Firestore transaction reserves **one attempt per rolling 24 hours per user**,
across channels, including failures and UTC midnight. The demo is blocked in middleware
and in the service. All storage is under `users/{uid}`; source writes also check the
connection and account deletion markers. Disconnecting disables that head, and account
deletion already removes calibration and cooldown records.

Existing runs apply the chosen head **at read time**, using only saved curve points and
three calibration/connection document reads. The saved baseline recovers its shared
prediction scale from the pinned generic model; a version/training-date mismatch or
missing/degenerate baseline falls back with a re-review explanation. The content scores
and driver explanations remain from the original model; the drop-off baseline changes,
then lift peaks/dips are reselected and linked to overlapping owned findings (one extra
findings query when markers exist). Saved runs remain generic snapshots, and no inference
or Firestore writes happen on these reads. Transcript-only runs still have no markers.
One selected channel applies across the workspace; a new attempt replaces its previous
active calibration, even if the new attempt fails or has insufficient data.

**Interpretation.** This adapts the drop-off shape to the creator's audience. Retention
and replay are different behaviours, even after within-video normalization. It is still
not a retention prediction, and there is no evidence yet that this baseline improves the
content model's ranking. The public-data metrics above do not evaluate channel calibration.
Recent-upload selection and the two broad duration buckets may poorly represent mixed
channels, new formats, live streams or very long videos. YouTube can withhold low-traffic
retention reports, so small channels may keep the generic head.

**Verification, 14 October 2026.** Read-only provider calls on the channel used by the
previous calendar checks made exactly **5 YouTube requests**: one `playlistItems.list`,
one `videos.list`, one Analytics views report and two retention reports. The channel had
two uploads and zero qualifying curves, so the stored/read-back state was
`insufficient_data`; a second service attempt was rejected by the live cooldown. One
OAuth token refresh was needed (outside the five YouTube requests). The local passphrase
cipher initially did not match the stored KMS tokens; rerunning the already reserved
attempt with KMS succeeded. No YouTube writes and **0 Gemini calls** were made.
A fabricated 40-video response verified the 43-request bound, column-name parsing,
shrinkage, minimum data rule, flat-curve rejection, read-time baseline/marker changes,
original-curve preservation, finding links, old-model fallback, ownership, demo blocking
and cooldown. The signed-in read-only demo info panel was checked in the collaborative browser, and
an authenticated calibration POST was rejected with HTTP 403 before reaching the provider.
A channel with sufficient live retention and the editable calibration UI remain unverified.

## Reproduce

From the repository root:

```bash
# Creator set (resumable). Captions via the transcript API, or local Whisper if blocked.
uv run --project backend python backend/scripts/interest_collect.py meta --target 250
uv run --project backend --with youtube-transcript-api \
    python backend/scripts/interest_collect.py subs
uv run --project backend --with mlx-whisper --with curl_cffi \
    python backend/scripts/interest_collect.py asr

# Corpus parquet files
mkdir -p evals/interest/raw/cbc
curl -L -o evals/interest/raw/cbc/train.parquet "https://huggingface.co/datasets/behavior-in-the-wild/content-behavior-corpus/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"
curl -L -o evals/interest/raw/cbc/test.parquet "https://huggingface.co/datasets/behavior-in-the-wild/content-behavior-corpus/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet"

# Gemini signals (bounded and cached), then train and evaluate
uv run --project backend --with pyarrow \
    python backend/scripts/interest_train.py signals --max-calls 2500
uv run --project backend --with pyarrow python backend/scripts/interest_train.py train

# Add curves and coverage to existing analysis runs (bounded)
uv run --project backend python backend/scripts/interest_backfill.py --uid <uid> --max-runs 10
```

`train` writes [results.json](results.json), [videos.csv](videos.csv) and the bundled model.
`--dry-run` reports without writing.
