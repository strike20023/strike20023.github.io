# From the First Readable Token to Speech: Optimizing a Qwen3-TTS Streaming Pipeline

October 21, 2026 · [中文版](2026-10-21-qwen3-tts-streaming-optimization.zh.md)

The LLM was already displaying text quickly, but speech was still arriving late. The goal of this experiment was more demanding than generating a complete answer and playing it in chunks: **start synthesizing as soon as the first readable token arrives, without waiting for subsequent words or a sentence, then continue reading incoming text.**

In one before-and-after browser comparison using the same question and identical response text, estimated audible onset fell from **1,513ms to 550ms**, and generation completion fell from **22.12s to 7.22s**. A separate fixed-text TTS comparison reduced generation time from **8.41s to approximately 2.80s**.

This is a deployment case study, not a model leaderboard. We did not achieve sub-100ms onset, nor establish that arbitrary text and arrival patterns will always be read without omissions.

## Pipeline and environment

The experiment uses `Qwen3-TTS-12Hz-0.6B-CustomVoice`, available from the [official Qwen3-TTS repository](https://github.com/QwenLM/Qwen3-TTS). We kept the model and optimized inference and delivery. We did not train a new model or replace it with a Qwen-Omni Talker.

```text
Browser sends a question
    │ one WebSocket
    ▼
Web service ──streaming request──► 27B text LLM
    │                                  │
    │◄──────── text deltas ─────────────┘
    ├──► immediate text updates in the browser
    └──► incremental text queue
                  │
                  ▼
            TTS Talker backbone
                  │ first codebook
                  ▼
            MTP / residual code prediction
                  │ complete audio codes
                  ▼
            causal waveform decoding → PCM
                  │ same WebSocket
                  ▼
            scheduled Web Audio playback
```

The web service, LLM, and TTS run on the same server. TTS uses one RTX 4090 D; the LLM runs on other GPUs. The TTS service admits one session at a time, so these results exclude multi-user queueing. The backbone and MTP use BF16; the final waveform decoder uses FP32. The environment was `qwen-tts 0.1.1`, `transformers 4.57.3`, and `torch 2.14.1`, with SDPA for the backbone. Main comparisons used Chinese, the Vivian voice, and a warmed service.

## Separate the latency measurements first

The first PCM packet may contain no speech. Server-side generation completion is also different from playback completion. We recorded these separately:

| Metric | Definition |
| --- | --- |
| First text | Send click → first LLM text delta received |
| First PCM | Send click → first binary PCM packet received |
| First non-silent packet | Send click → a PCM packet containing a sample above the silence threshold |
| Estimated audible onset | Estimate from the first non-silent sample's offset, Web Audio scheduling, and available `outputLatency` |
| Generation completion | Send click → server `done` event |
| Playback underrun | Accumulated time by which the playback cursor has fallen behind the audio clock when more audio arrives |

Estimated onset is not a microphone measurement of a physical speaker. An amplitude threshold is not proof that a sample contains correct speech, either. That requires additional content checks.

## 1. Feed incremental text into synthesis

Streaming input and streaming output are different capabilities. Splitting an already completed waveform into packets demonstrates output streaming, not that the model can consume unfinished text.

Our adapter supplies the next text embedding from a queue during audio generation. Unconsumed text can be tokenized together again; tokens already committed to the model are not rewritten. Chinese tokenization requires care around byte fragments: tokenizer offsets are used to commit the pieces covering the first complete character together, rather than dropping part of a character.

When text temporarily runs out, the final implementation:

1. Sends a text-end marker for the current model segment and lets it finish speaking the known content.
2. Continues emitting generated audio instead of blocking playback.
3. Starts another model segment when more text arrives, within the same WebSocket session.

KV state is retained within a segment and rebuilt between segments. This is not an indefinitely continuous Omni Talker state that can wait forever for new text.

If the only available text is “你,” there is nothing else to read once that character finishes. A pause is appropriate. **The system cannot simultaneously avoid waiting, keep producing meaningful speech indefinitely, and never invent missing content.** The first-token requirement means that speaking the known character must not depend on future text; it does not imply zero computation time.

## 2. Accelerate MTP by capturing the fixed residual-prediction loop

Here, MTP refers to the residual code predictor. After the backbone produces the first codebook, this configuration predicts 15 residual codebook tokens. We optimized execution of those fixed steps; we did not remove their autoregressive dependencies or turn them into 15 parallel predictions.

The implementation uses CUDA Graphs with a KV cache:

- Allocate fixed-shape input, position, and output buffers.
- Unroll the 15 steps with their actual dependencies: embeddings at the first step, then the preceding token.
- Retain the captured graph, cache-related tensors, and output buffers for replay.
- Copy each new Talker hidden-state input into the static buffer before replaying.
- Preserve the configured sampling settings: top-k 50, temperature 0.9, and top-p 1.0.

This reduces repeated Python dispatch and general-purpose `generate()` overhead. Fixed shapes alone are insufficient: cache handling, positions, and tensor lifetimes must also be correct.

Passing a random-tensor smoke test was not enough. During startup, the service compares graph greedy outputs against upstream greedy outputs for **32 real Talker inputs**, requiring exact token agreement before accepting requests. This does not establish sample-by-sample equivalence for stochastic generation. CUDA Graph execution can change random-number consumption, so a fixed seed is not a guarantee of identical waveforms.

## 3. Decode only the required causal context

The previous path repeatedly decoded the entire audio prefix and discarded samples already sent. As a response grew, so did redundant work.

The final path retains 25 frames of left context, decodes that context plus new frames, and uses CUDA Graph buckets of 8, 16, and 32 frames. Inputs larger than the available buckets fall back to ordinary decoding. Each frame represents 1,920 samples at 24kHz: 80ms of audio content, not necessarily 80ms of computation.

Before audible content is detected, decoding is attempted on each frame; afterward, the default cadence is one chunk per four frames. The implementation therefore does not intentionally delay onset to fill a four-frame chunk. First-packet latency, sustained throughput, and playback underrun still need separate measurement.

The output slicing can be summarized as:

```python
sent_frames = samples_sent // 1920
start = max(0, sent_frames - 25)
selected = codes[start:]
wave = decode_with_bucket(selected)
new_pcm = wave[(sent_frames - start) * 1920 : len(selected) * 1920]
```

This is explanatory pseudocode, not a complete implementation. The important properties are that left context is not emitted twice, right padding is discarded, and future text is unnecessary.

BF16 waveform decoding showed noticeable numerical differences across input lengths. We therefore moved only the waveform decoder to FP32 while keeping CUDA Graph acceleration. Across eight startup checks on real frames, the maximum absolute difference from ordinary decoding with the same left context was approximately **0.000653**, below the configured 0.003 threshold.

This is a bounded numerical check, not proof of perceptual equivalence for every sequence length. Changes to the decoder or context window require renewed boundary validation.

## 4. Diagnose leading silence instead of counting silent packets as low latency

For the same fixed input, the original version, the MTP-only optimization, and the decoder-accelerated version all first crossed an absolute waveform amplitude of 0.001 at approximately **365ms into the generated audio**. That places the dominant leading silence for this sample in the generated waveform, rather than in a 365ms browser buffer.

We process only the beginning of each request. Already generated low-amplitude samples are accumulated until an onset is detected; 40ms before that onset is retained, and the earlier prefix is removed. Approximately 325ms was removed in the fixed-text test and 353ms in the browser comparison. Later natural pauses are not trimmed by this rule.

Trimming does not make the model compute speech that does not yet exist. There are two separate gains: generating useful frames sooner and avoiding playback of their preceding silence. The 40ms margin helps preserve quiet onsets, but amplitude gating remains a heuristic that needs coverage across initial phonemes and voices.

## 5. Include the WebSocket and player in the inference pipeline

The server forwards each LLM delta both to the browser and to TTS. Visible text updates do not wait for speech completion. Audio metadata and binary PCM travel over the same WebSocket; the client checks request association before scheduling playback.

The player maintains a continuous cursor instead of starting every packet independently at arrival time:

```javascript
const when = Math.max(cursor, audioContext.currentTime + 0.012);
source.start(when);
cursor = when + buffer.duration;
```

The 12ms margin is a local scheduling choice, not a universal optimum. Stopping clears local audio, discards late packets, cancels remote generation, and releases the single-session lock. Otherwise, the next measurement may include leftover playback or queueing from the previous request.

A later nine-voice selector changes the request's speaker while reusing the streaming and graph paths. Direct intranet HTTP access also exposed an unavailable `crypto.randomUUID()` API. Request correlation now has a timestamp-plus-page-sequence fallback. These IDs are not authentication tokens, and this fallback should not be used for security tokens.

## Results: end-to-end and fixed-text tests answer different questions

The browser comparison asked for two sentences about places to walk in Hangzhou. The returned text was identical before and after optimization:

| Metric | Before | After |
| --- | ---: | ---: |
| First text | 697ms | 265ms |
| First PCM | 861ms, including silence | 453ms |
| Estimated audible onset | 1,513ms | 550ms |
| First text → estimated onset | 816ms | 285ms |
| Generation completion | 22.123s | 7.216s |
| Audio duration | 16.80s | 16.45s |
| Accumulated playback underrun | 4,044ms | 0ms |

LLM first-text latency also improved in this pair. Attributing the entire end-to-end difference to TTS would be incorrect. These are individual observations, not p50 or p95 statistics.

A separate TTS test used fixed text and seed 42:

> 你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。

| Metric | Original | Final, run 1 | Final, run 2 |
| --- | ---: | ---: | ---: |
| Generation time | 8.415s | 2.803s | 2.794s |
| First non-silent packet | 634ms | 183ms | 189ms |
| Estimated onset | 682ms | 226ms | 231ms |
| Output audio duration | 6.640s | 6.315s | 6.315s |

Generation was approximately three times faster. The duration reduction largely corresponds to removing the roughly 325ms leading prefix. The final fixed-text playback simulation still had approximately 58ms of underrun, so the browser run's zero underrun must not be generalized to all inputs.

## Prove independence from future text, then check omissions and repetition

The most direct test is to withhold the rest of the text. Four trials first supplied “你,” “你,” “我,” and “请,” delaying subsequent text by 2, 2, 5, and 2 seconds. The first non-silent packets arrived at approximately 219, 252, 218, and 218ms.

We extracted **only audio already received before the second text delta arrived** and ran ASR on those prefixes. The recognized results were respectively “你,” “你,” “我,” and “请.” This prevents audio generated after future text becomes available from being counted as evidence of first-token behavior.

The final regression set contained 13 scenarios, including a wait-for-text control, plus four prefix excerpts: 17 ASR comparisons in total.

- Fifteen matched character for character.
- Two contained homophonic substitutions: “先→仙” and “步→不.”
- ASR detected no deletions or insertions.

Three actual LLM-streaming trials also aligned character for character. Two additional complete `/chat` recordings after deployment produced one exact match and one “胜地→圣地” homophonic substitution, with no detected omissions or repetitions. Cancellation and disconnection released the session both during generation and while waiting for text; cancelling and reusing the same connection also passed.

ASR can miss or misclassify pronunciation defects. These are acceptance observations, not a substitute for listening tests or a guarantee of perfect reading on arbitrary input.

## Failed attempts matter

An earlier accelerated candidate generated extra speech. We tried fully greedy backbone generation and then a deterministic tail only after a fragmented request ended. Both introduced omissions, so both were withdrawn. The deployed version preserves the original sampling approach and optimizes execution and decoding instead.

Finishing sooner is not the same as reading everything. Truncating tails, forcing EOS, or changing sampling may improve a timing number while damaging content. Evaluation must retain text, event timing, and complete audio, rather than only first-packet latency.

## What remains to be measured

The next checks should cover a wider range of initial phonemes and languages, full reading accuracy across all nine voices, network jitter, long responses, concurrent queueing, cold starts, and p95 latency. The 25-frame window and silence threshold also need broader perceptual validation.

The useful method is to separate packet arrival from audible onset, separate LLM latency from TTS computation, withhold future text to test input streaming, and inspect complete audio before deploying. **This experiment reached audible onset in hundreds of milliseconds; it did not demonstrate sub-100ms end-to-end voice interaction.**

*Data note: measurements come from the single-session experiments on October 21, 2026. This public article includes methods and results, but not internal service addresses, session logs, model weights, or the complete deployment source. Code snippets explain the approach; they are not a turnkey reproduction package.*
