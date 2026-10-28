---
title: Qwen3-TTS 流式链路优化
description: 独立文本 LLM 与 Qwen3-TTS 串接系统的低延迟语音实践。
date: 2026-10-21
tags:
  - speech/tts
---

# Qwen3-TTS 流式链路优化

研究独立文本 LLM 与 Qwen3-TTS 串接时，从首个可读字符到语音播放的延迟。内容包括瓶颈测量、CUDA Graph、增量解码，以及用于复现实验的推理与服务代码。

## 阅读

- [从首个可读 token 到出声：一次 Qwen3-TTS 流式链路优化](optimization.zh.md)

## 复现

[复现指南](repro/README.md)包含环境、启动方法和测量步骤。

- [基线分析数据](repro/baseline-profile.json)
- [验证结果](repro/validation-result.json)
- [源码目录](https://github.com/strike20023/strike20023.github.io/tree/main/blogs/qwen3-tts-streaming/repro)
