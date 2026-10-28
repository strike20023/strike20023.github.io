# Qwen3-TTS streaming reproduction kit

[中文技术文章](../optimization.zh.md) · [English technical article](../optimization.en.md)

This directory contains an executable snapshot of the experimental serving and benchmark code. Internal addresses and LLM identifiers have been replaced by environment variables. It is a single-session research implementation, not an upstream Qwen API or a production serving framework.

## What is actually running?

- **Inference:** native PyTorch + `qwen-tts`, using Hugging Face Transformers generation, SDPA, and `DynamicCache`. No vLLM, SGLang, TensorRT, `torch.compile`, FlashAttention package, quantization, or new training in this TTS acceleration path.
- **Acceleration:** `torch.cuda.CUDAGraph` for the residual predictor and waveform decoder. The Talker backbone still uses its ordinary generation path.
- **Service:** FastAPI + Uvicorn, one worker, one TTS session protected by a lock. A Python thread runs inference; `loop.call_soon_threadsafe` forwards events to an asyncio queue.
- **LLM bridge:** HTTPX reads an OpenAI-compatible SSE chat-completions stream. The LLM endpoint is separate from the TTS code; use any compatible model that returns text in `choices[].delta.content`.
- **Browser:** plain HTML/JavaScript, one WebSocket, little-endian signed PCM16 at 24kHz, Web Audio scheduling. No frontend build step.

## Observed environment, not a clean-install guarantee

| Component | Observed value |
| --- | --- |
| OS | Ubuntu 22.04.1 LTS, Linux 5.15, x86-64, glibc 2.35 |
| Python | CPython 3.11.12 |
| GPU / driver | RTX 4090 D 24GB / 580.126.20 |
| PyTorch / compiled CUDA | 2.14.1 / 13.0 |
| cuDNN | 9.24 (`torch.backends.cudnn.version() == 92400`) |
| torchaudio | 2.11.0 |
| qwen-tts / Transformers | 0.1.1 / 4.57.3 |
| accelerate / tokenizers | 1.12.0 / 0.22.2 |
| FastAPI / Uvicorn | 0.151.0 / 0.54.0 |
| HTTPX / websockets | 0.28.1 / 17.3 |
| NumPy / soundfile | 2.4.6 / 0.14.0 |
| huggingface-hub / safetensors | 0.36.2 / 0.8.0 |

[requirements-observed.txt](requirements-observed.txt) is the installed-package inventory from the working server. It is **not a resolver-generated lockfile** and contains optional packages not used by this path. In particular, torch and torchaudio have different version numbers. Do not infer binary compatibility from the inventory. A fresh installation of this full snapshot has not been validated; changing the torch/CUDA combination requires passing the startup checks again. Wheel hashes are not supplied, so exact bitwise recreation is not claimed. All 13 cached download metadata records, including both weight files, identify model revision `85e237c12c027371202489a0ec509ded67b5e4b5`; the download command pins that revision.

The model configuration files used in the run had these SHA-256 values:

```text
81aca2b6fac304944d8acf345272d8a9a727d5fc2e2e66b222ab4729340c7455  config.json
f1b90b4513f3b34c62851049e2492d7b4c5940daf1276f89c82b8ef04127f3aa  generation_config.json
```

These identify configuration files, not the model weights.

## 1. Prepare an environment

Use a Linux NVIDIA CUDA environment. The captured path is not implemented for CPU or Apple MPS. The original single-session accelerated process used approximately 3.5GB of GPU memory after warmup; this is an observation, not a guaranteed minimum.

From the repository root:

```bash
cd blogs/qwen3-tts-streaming/repro
uv venv --python 3.11.12 .venv
source .venv/bin/activate

# First try normal dependency resolution against the observed inventory.
uv pip install -r requirements-observed.txt
```

If the resolver rejects the snapshot, do not silently upgrade the inference packages. To reconstruct the installed inventory for a controlled experiment, `uv pip install --no-deps -r requirements-observed.txt` installs the listed versions without resolving their relationships; **it does not fix ABI incompatibility**. Record any installation/import failures. Alternatively, install a mutually supported torch/torchaudio pair for your driver, retain `qwen-tts==0.1.1` and `transformers==4.57.3`, and treat that as a new environment requiring validation rather than the original benchmark environment.

Download the model, or set `MODEL` to an existing local directory:

```bash
hf download Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice \
  --revision 85e237c12c027371202489a0ec509ded67b5e4b5 \
  --local-dir ./models/Qwen3-TTS-12Hz-0.6B-CustomVoice
export MODEL="$PWD/models/Qwen3-TTS-12Hz-0.6B-CustomVoice"
sha256sum "$MODEL/config.json" "$MODEL/generation_config.json"
python -c 'import torch,qwen_tts; print(torch.__version__,torch.version.cuda,torch.cuda.is_available())'
python -m unittest test_queue -v
```

Loading by the default Hugging Face identifier may resolve a different revision. For this experiment use the pinned download command and pass the resulting local directory through `MODEL`. Model and dependency licenses remain those of their respective upstream projects.

## 2. Run the accelerated TTS server

```bash
export CUDA_VISIBLE_DEVICES=0
FAST_INFERENCE=1 TRIM_LEADING_SILENCE=1 bash run.sh
```

Default address: `http://127.0.0.1:8092/`. `HOST` and `PORT` override the binding. One worker is required: the graph buffers are shared mutable state and are not safe for overlapping sessions. Do not expose the unauthenticated demo directly to an untrusted network.

Startup captures the graphs, runs a warmup sentence, checks 32 real residual-predictor inputs against upstream greedy generation, and checks eight codec outputs against ordinary decoding with the same left context. A mismatch aborts startup; do not remove the assertions to make an incompatible version appear to work.

Expected log markers:

```text
MTP: 32 real Talker inputs matched upstream greedy
Codec real-frame check ...
Application startup complete.
```

The order of the first two markers can differ. In another terminal:

```bash
curl http://127.0.0.1:8092/health
```

Expect `ready`, `fast_inference`, and `trim_leading_silence` to be true. Health alone is not proof of successful synthesis; run the tests below.

## 3. Fixed-text benchmark without an LLM

```bash
python bench.py --mode full --runs 3 --seed 42 --chunk-frames 4 \
  --text '你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。' \
  --output outputs/fast-fixed
```

Each run writes a WAV and a JSON with summary metrics and individual text/audio events. Discard the first measured run if comparing against a baseline that has not been warmed. Do not report service startup/graph capture as warmed inference latency.

To measure the baseline, stop the server with Ctrl-C, then restart in a separate process:

```bash
FAST_INFERENCE=0 bash run.sh
# In another terminal, after startup:
python bench.py --mode full --runs 3 --seed 42 --chunk-frames 4 \
  --text '你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。' \
  --output outputs/baseline-fixed
```

`FAST_INFERENCE=0` uses the same text adapter, but ordinary residual generation and full-prefix waveform decoding. In this snapshot, silence trimming is enabled inside the fast initialization branch, so the baseline also has no leading-silence trim. To isolate acceleration from trimming, run a third process with `FAST_INFERENCE=1 TRIM_LEADING_SILENCE=0`. Do not toggle graph installation or dtype on a live model object.

Measure first non-silent PCM as well as first PCM. Compare generated duration and complete transcript, not just elapsed time. `bench.py` reports summary times relative to its `request_start` event, after opening the WebSocket; the playback simulation starts at the first PCM packet. Its playback simulation omits browser scheduling and hardware output latency and must not be equated with the browser's displayed onset.

## 4. Strict first-character test

Restart the fast server if it is not already running:

```bash
python bench.py --mode hold --delay 5 --seed 44 --runs 1 \
  --text '我喜欢读书，也喜欢听音乐。' --output outputs/hold-five-seconds
python check_prefix.py outputs/hold-five-seconds
```

The client sends `我`, waits five seconds, and sends the rest. `check_prefix.py` extracts only PCM received before the second text delta. Listen to `hold-0-prefix.wav`: it must contain the first character, not merely noise. Run your ASR on both the prefix and full WAV and compare against their adjacent JSON text. No ASR service is bundled. The original evaluation used Qwen3-ASR-1.7B, with punctuation-normalized character alignment; ASR errors must be distinguished from TTS errors.

Additional arrival patterns:

```bash
python bench.py --mode chars --delay .25 --seed 46 \
  --text '今天先喝水，然后吃饭，最后散步。' --output outputs/chars
python bench.py --mode jitter --delay .6 --seed 47 \
  --text '请记住三个词：苹果、火车、太阳。' --output outputs/jitter
```

The default starvation policy is `segment`. `wait` is a diagnostic control that waits for more text; `pad` is experimental and can omit speech. Neither is evidence of satisfying the default strict first-character contract.

## 5. Connect an LLM and use the browser

Set these variables **before** starting the server:

```bash
export LLM_URL='http://127.0.0.1:8001/v1/chat/completions'
export LLM_MODEL='your-served-model-name'
# If required, supply LLM_API_KEY through your environment; never commit it.
bash run.sh
```

The example sends `chat_template_kwargs: {enable_thinking: false}`. Remove that model-specific extension if your endpoint rejects it. The reported 27B backend is not packaged here; using a different endpoint reproduces the integration, not the exact end-to-end latency.

Open `http://127.0.0.1:8092/`, choose a voice, and send a question. WebSocket URLs follow the page origin automatically. The HTTP request-ID fallback is included. Use `python bench_chat.py --runs 3 --output outputs/chat` to capture the same `/chat` protocol's text and PCM without the browser.

## Source map and invariants

| File / function | Responsibility |
| --- | --- |
| `streaming.py:install_adapter` | Extracts the installed Talker `forward` source, asserts a known source anchor, and binds a modified method in memory. Upstream package files are not edited. This is intentionally version-sensitive. |
| `LiveSession.take_group` | Uses tokenizer offsets to commit a complete character's pieces. |
| `LiveSession.next_embedding` | Consumes queued text, distinguishes temporary starvation from request EOF, and emits text EOS for a segment. |
| `LiveSession.on_codes/decode` | Decodes every frame until audible content, then at the configured cadence; tracks untrimmed sample count independently of emitted PCM. |
| `fast_inference.py:install_mtp` | Captures separate greedy and sampled residual graphs. Input is `[1, 2, talker_hidden_size]`; first positions are `[0,1]`, followed by one position per step. Each replay begins the same within-frame residual sequence; this cache does not span audio frames. |
| `CodecGraph.decode_new` | Uses `[1, num_quantizers, frames]` code tensors, 25-frame left context, 8/16/32-frame buckets, and crops only new real samples. |
| `server.py:load` | Installs the adapter, optional graphs, and pre-serving validation. |
| `web_chat.py:turn` | Runs HTTPX SSE ingestion and TTS generation concurrently; streams text, audio metadata, and PCM. |
| `web.html` | Maintains request IDs, a playback cursor, voice selection, and cancellation of scheduled audio. |

Never treat zero-filled right padding as future content; never emit that region. Never use the number of trimmed samples to advance the decoder's untrimmed frame counter. Never run two inference threads against the same graph buffers.

## Reproduction status

The supplied code is derived from the measured implementation; the core `streaming.py` and `fast_inference.py` are copied without algorithm changes. LLM settings are parameterized, the launcher is portable, and the full installed-package inventory is supplied. A fresh full dependency installation has not been validated. Reusing the observed runtime checks algorithm integration, not clean-install reproducibility. Exact timings remain hardware-, driver-, load-, input-arrival-, and model-dependent.

### Public snapshot execution check (2026-10-21)

The published Python source was copied into a separate directory and started as an isolated server using the original installed Python environment. Five queue tests and all startup graph checks passed. Fixed-text generation took 2.778s, with first non-silent PCM at 199ms; a five-second withheld-text trial returned first non-silent PCM at 217ms. See [validation-result.json](validation-result.json). This validates source integration in the observed runtime, **not** a fresh installation of the dependency inventory.

The withheld-text prefix was independently transcribed as “我。” and the complete waveform as “我喜欢读书，也喜欢听音乐。” with Qwen3-ASR-1.7B.

### Reproduce the component profile

Stop the serving process first, use the same model and CUDA device environment, and run `python profile_stream.py`. This loads a separate **unaccelerated** model, synchronizes CUDA around residual-predictor and waveform-decoder calls, and writes `outputs/profile-strict/*.json`. The third trial deliberately withholds subsequent text. Compare warmed fixed-text trials, not the hold trial. [baseline-profile.json](baseline-profile.json) is the summarized original measurement used for the article's bottleneck discussion. Synchronization perturbs execution; this is region timing, not a GPU kernel timeline.
