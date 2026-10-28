#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export MODEL="${MODEL:-Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export FAST_INFERENCE="${FAST_INFERENCE:-1}"
export TRIM_LEADING_SILENCE="${TRIM_LEADING_SILENCE:-1}"
export TALKER_SAMPLE="${TALKER_SAMPLE:-1}"
exec "${PYTHON:-python}" -m uvicorn server:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8092}" --workers 1
