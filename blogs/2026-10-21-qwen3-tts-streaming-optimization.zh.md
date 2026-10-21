# 从首个可读 token 到出声：一次 Qwen3-TTS 流式链路优化

2026-10-21 · [English](2026-10-21-qwen3-tts-streaming-optimization.en.md)

LLM 的文字已经快速刷出来，声音却迟迟没有开始——这是把一个文本模型接到 TTS 时很容易遇到的问题。这次实验的目标不是“先生成完整回答，再分块播放”，而是：**第一个可读 token 到达后就开始合成，不等待后面的词或句子；后文到来时继续朗读。**

最终，在同一个浏览器、同一个问题且返回文字相同的一组前后对照中，预计出声从 **1513ms 降到 550ms**，生成完成从 **22.12 秒降到 7.22 秒**。单独用固定文本测试 TTS，生成耗时从 **8.41 秒降到约 2.80 秒**。

这是一份实际部署的工程记录，不是模型排行榜。我们没有达到低于 100ms 的起音，也没有证明任意文本、任意网络节奏下都不会漏读。

## 可运行代码、框架和精确版本

现在提供[复现实验目录](qwen3-tts-streaming-repro/README.md)，包含完整的推理适配器、CUDA Graph 实现、FastAPI 服务、浏览器页面和基准客户端；不再只有伪代码。可先不接 LLM，仅用 `/ws` 跑固定文本，再接 `/chat` 测端到端。

| 层 | 实际实现与版本 |
| --- | --- |
| 操作系统与 GPU | Ubuntu 22.04.1、RTX 4090 D 24GB、NVIDIA driver 580.126.20 |
| Python | CPython 3.11.12 |
| 张量计算 | PyTorch 2.14.1，编译 CUDA 13.0，cuDNN 9.24 |
| TTS 包 | qwen-tts 0.1.1 |
| 生成框架 | Transformers 4.57.3、accelerate 1.12.0、tokenizers 0.22.2 |
| HTTP / WebSocket 服务 | FastAPI 0.151.0、Uvicorn 0.54.0，单 worker |
| 客户端传输 | HTTPX 0.28.1、websockets 17.3 |
| 数值与音频文件 | NumPy 2.4.6、soundfile 0.14.0 |

TTS 路径使用原生 PyTorch 和 Transformers，**没有使用 vLLM、SGLang、TensorRT、`torch.compile`、量化或新训练**。注意力实现是 SDPA；CUDA Graph 加速的是残差预测器和波形 decoder，Talker 主干仍走普通生成路径。Web 前端是原生 JavaScript，没有构建步骤。

[完整依赖快照](qwen3-tts-streaming-repro/requirements-observed.txt)来自已运行环境，而不是重新求解的 lockfile。特别是环境里的 torchaudio 为 2.11.0，与 torch 版本不一致；不能据此推断这是一组推荐的二进制兼容版本。完整快照的全新环境安装尚未验证，已从下载缓存的13份元数据（含两个权重文件）核对模型 revision 为 `85e237c12c027371202489a0ec509ded67b5e4b5`。下面命令固定该版本，但仍不承诺跨环境逐 bit 相同的声音。

### 快速复现顺序

```bash
git clone https://github.com/strike20023/strike20023.github.io.git
cd strike20023.github.io/blogs/qwen3-tts-streaming-repro
uv venv --python 3.11.12 .venv
source .venv/bin/activate
uv pip install -r requirements-observed.txt

hf download Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice \
  --revision 85e237c12c027371202489a0ec509ded67b5e4b5 \
  --local-dir ./models/Qwen3-TTS-12Hz-0.6B-CustomVoice
export MODEL="$PWD/models/Qwen3-TTS-12Hz-0.6B-CustomVoice"
export CUDA_VISIBLE_DEVICES=0
python -m unittest test_queue -v
FAST_INFERENCE=1 TRIM_LEADING_SILENCE=1 bash run.sh
```

如果依赖求解失败，见复现目录中对已安装快照、`--no-deps` 和匹配 torch/torchaudio 版本的说明；不要静默升级后仍把结果标成原环境复现。服务启动自检不通过时，也不要删除断言继续跑。

另开终端，在相同环境、相同目录运行：

```bash
# 不经过 LLM，先隔离 TTS；输出完整 WAV 和逐事件 JSON。
python bench.py --mode full --runs 3 --seed 42 --chunk-frames 4 \
  --text '你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。' \
  --output outputs/fast-fixed

# 只先发“我”，五秒后才发后文。
python bench.py --mode hold --delay 5 --seed 44 \
  --text '我喜欢读书，也喜欢听音乐。' --output outputs/hold
python check_prefix.py outputs/hold
```

对照必须分进程：停止服务后以 `FAST_INFERENCE=0 bash run.sh` 启动，再跑同一组命令、写入新的输出目录。丢弃未预热的测量轮。该 baseline 同时关闭 graph 和开头静音裁剪；增加 `FAST_INFERENCE=1 TRIM_LEADING_SILENCE=0` 的第三组，才能进一步分离计算加速和静音裁剪的收益。

接 LLM 时，在启动服务前设置 `LLM_URL` 为完整的 OpenAI 兼容 chat-completions URL、`LLM_MODEL` 为服务中的模型名，需要鉴权时通过 `LLM_API_KEY` 环境变量传入。页面位于 `http://127.0.0.1:8092/`。不同 LLM 能复现连接方式，但不能复现本文的 LLM 延迟。若服务不接受 `chat_template_kwargs`，应移除这个模型专用参数。复现包不包含 ASR 服务；首字和全文的 ASR 需另外提供，原评估使用 Qwen3-ASR-1.7B。

### 从函数看实现细节

**输入适配：** [`install_adapter()`](qwen3-tts-streaming-repro/streaming.py) 通过 `inspect.getsource` 获取当前安装包的 Talker `forward`，在已断言存在的文本 embedding 分支插入队列消费逻辑，再把新方法绑定到模型实例；没有修改 site-packages。这个方法依赖确切源码结构，升级 qwen-tts/Transformers 后需要重新核查。尚未给当前段提供文本 EOS 时屏蔽 codec EOS，避免模型在已知文字未消费完时结束；`pending`、未读字符串和队列终止标记必须分开处理。

**MTP 缓冲与位置：** [`install_mtp()`](qwen3-tts-streaming-repro/fast_inference.py) 的静态输入形状为 `[1, 2, talker_hidden_size]`。首步位置是 `[0,1]`，随后第 `i` 个残差步使用位置 `[i+1]`，`generation_steps=i` 决定相应预测步骤。`DynamicCache` 在捕获的一个音频帧残差序列内使用，不是跨音频帧无限累积的 cache。greedy 和 sampling 分别捕获 graph；sampling 在 GPU 上做温度缩放、top-k 截断、softmax 和 multinomial。replay 后复制输出，避免后一次 replay 覆盖尚在使用的结果。

**捕获与执行：** 先在独立 CUDA stream 上预热，再与当前 stream 同步，随后捕获。不能把 graph 当作普通无状态函数：它引用固定缓冲区，所以服务用锁限制单会话、Uvicorn 固定一个 worker。开启多个推理线程共享这些 buffers 会互相覆盖输入输出，不能直接用它测试并发吞吐。

**解码与计数：** codes 转成 `[1, num_quantizers, frames]`，挑最小可容纳的桶，清零缓冲区、拷贝实际帧、replay。`samples_sent` 计算的是未裁静音前的模型采样数；发往浏览器的样本数可以更少。混用两个计数会导致后续波形切片错位，表现为漏音或重复。

**线程与事件循环：** [`web_chat.py`](qwen3-tts-streaming-repro/web_chat.py) 用 HTTPX 异步读取 LLM SSE，独立 Python 线程执行 GPU 推理；推理事件通过 `loop.call_soon_threadsafe` 送入 asyncio 队列。这里的异步是让文本输入、推理和传输能够交错进行，不是并发运行多个 TTS 请求。

### 复现时应看到什么

服务启动应出现 `MTP: 32 real Talker inputs matched upstream greedy` 和 codec 对照日志，随后才开始接受请求。固定文本测试应产生 `full-*.wav/json`；严格首字测试应产生 `hold-0-prefix.wav`，且其中应能识别出“我”。不要仅凭 `/health` 成功或 prefix 文件非空判定通过。

`bench.py` 的 summary 从 WebSocket 建立后的 `request_start` 计时，播放模拟从首 PCM 开始，不含浏览器的 12ms 排程余量和物理输出延迟。因此客户端基准的预计起音与浏览器显示值不能直接当作同一个指标。


## 链路与实验环境

[Qwen3-TTS 官方仓库](https://github.com/QwenLM/Qwen3-TTS)提供了本实验使用的 `Qwen3-TTS-12Hz-0.6B-CustomVoice`。我们保留这个模型，在推理和传输路径上优化，没有训练新模型或替换成 Qwen-Omni Talker。

```text
浏览器发送问题
    │ 一个 WebSocket
    ▼
Web 服务 ──流式请求──► 27B 文本 LLM
    │                      │
    │◄──── 文本 delta ──────┘
    ├──► 浏览器立即显示文字
    └──► 增量文本队列
              │
              ▼
        TTS Talker 主干
              │ 首码本
              ▼
        MTP / 残差码本预测
              │ 完整音频 codes
              ▼
        因果波形解码 → PCM
              │ 同一个 WebSocket
              ▼
        Web Audio 排队播放
```

Web、LLM 和 TTS 在同一台服务器上，TTS 使用一张 RTX 4090 D，LLM 在其他 GPU 上服务。TTS 是单会话实验服务，结果不包含多用户并发排队。主干和 MTP 使用 BF16，最终波形解码器使用 FP32；本次环境为 `qwen-tts 0.1.1`、`transformers 4.57.3`、`torch 2.14.1`，主干使用 SDPA。主要对照使用中文、Vivian 音色和预热后的服务。

## 先拆开“延迟”

第一包 PCM 不一定包含人声。服务端完成生成也不等于浏览器播放结束。因此我们分别记录：

| 指标 | 起点与终点 |
| --- | --- |
| 首文字 | 点击发送 → 收到首个 LLM 文本 delta |
| 首 PCM | 点击发送 → 收到首个 PCM 二进制包 |
| 首有效音频包 | 点击发送 → 收到包含非静音采样的 PCM 包 |
| 预计出声 | 根据首个非静音采样在包内的位置、Web Audio 排程和可用 `outputLatency` 估算 |
| 生成完成 | 点击发送 → 收到服务端 `done` |
| 播放断流 | 后续音频到达时，播放游标已经落后于音频时钟的累计时长 |

“预计出声”不是麦克风测出的物理扬声器起音。检测非静音使用绝对振幅阈值，它也不等于自动判断“这里一定是正确的人声”。后面还需要首字截取和 ASR 校验。

## 1. 让增量文本真正进入合成过程

输入流式和输出流式是两件事。把一段已经生成完的音频拆成小包，只解决了输出传输，不能证明模型接受了尚未结束的文本。

适配层在音频生成步中，从队列取下一份文本 embedding。没有读过的文字可以重新一起分词，已经送入模型的 token 不会回退重写。处理中文时还要考虑 tokenizer 的字节片段：根据 offset 把覆盖首个完整字符的片段一起提交，避免只交出半个字符或丢掉余下片段。

文字暂时断供时，最终实现选择：

1. 给当前模型段发送文本结束标记，让模型完成已知内容的音频。
2. 已生成的音频继续输出，不阻塞正在播放的内容。
3. 后文到达后，在同一个 WebSocket 会话内开始下一模型段。

KV cache 在段内保留，段间重建。这一点非常重要：它不是一个能无限等待新文字、永远不断开的 Omni Talker 状态。

如果只知道“你”，读完以后仍然没有后文，那么系统应当停顿。**不能同时要求不等后文、一直有声、又绝不猜测内容。** 这里的首 token 目标是“不依赖后文就能开始正确朗读已知字符”，不是“计算时间为零”。

## 2. 加速 MTP：减少固定残差预测循环的开销

这里把残差码本预测器简称为 MTP。主干生成首码本之后，当前配置还需要预测 15 个残差码本 token。优化的是这些固定步骤的执行方式，而不是让 15 个自回归依赖突然变成并行预测。

实现采用带 KV cache 的 CUDA Graph：

- 预分配固定形状输入、位置张量和输出缓冲区。
- 按模型实际依赖展开 15 步，首步使用 embedding，后续步骤使用上一步 token。
- 捕获并保留 graph、cache 所需张量和输出缓冲区；每次复制新的 Talker 隐状态，再 replay。
- 保留 top-k 50、temperature 0.9、top-p 1.0 的采样设置。

这种方法减少 Python 调度和通用 `generate()` 路径的重复开销。固定形状只是必要条件，cache、位置编码、张量生命周期也必须正确。

我们没有用随机张量上的“能跑通”作为验收。服务启动时取 **32 个真实 Talker 输入**，把 graph 的 greedy 输出与 upstream greedy 输出逐帧比较，要求完全一致，否则不接受请求。这个检查不意味着采样模式逐帧完全一致：CUDA Graph 下的随机数消耗顺序可能变化，同一个 seed 也不是声音逐样本相同的保证。

## 3. 加速解码：只算需要的因果上下文

原有路径反复解码整个音频前缀，再截取没有发过的部分。越往后，重复计算越多。

最终路径保留 25 帧左上下文，只解码这段上下文加新帧，采用 8、16、32 帧的 CUDA Graph 桶。超出桶范围时回退到普通解码。每帧对应 1920 个 24kHz 采样，即 80ms 的音频内容；这不是计算该帧必须花费 80ms。

首个可听内容出现前逐帧尝试解码，之后默认每 4 帧输出一块；因此没有为了凑齐一个 4 帧音频块而主动推迟起音。这个策略也解释了为什么首包延迟、后续吞吐与播放断流需要分别测量。

对新波形的裁切可写成如下示意：

```python
sent_frames = samples_sent // 1920
start = max(0, sent_frames - 25)
selected = codes[start:]
wave = decode_with_bucket(selected)
new_pcm = wave[(sent_frames - start) * 1920 : len(selected) * 1920]
```

这不是完整可运行实现。关键是：左上下文不重复发送，桶的右侧 padding 不发送，也不需要未来文字。

BF16 解码在不同输入长度下出现了明显数值偏差，因此没有坚持“所有模块都必须半精度”。最终只把波形 decoder 改为 FP32，仍使用 CUDA Graph。启动时 8 次真实帧对照中，与相同左上下文的普通 decoder 相比，最大绝对误差约 **0.000653**，低于设定的 0.003 阈值。

这是限定样本、限定上下文的数值检查，不是对所有长度的音质等价证明。修改窗口长度或 decoder 后仍需重新检查边界。

## 4. 查清前导静音，而不是拿静音包当低延迟

同一固定输入在原版、仅 MTP 加速、再加解码加速三个版本里，波形绝对振幅首次超过 0.001 都出现在约 **365ms 的音频位置**。这说明该样本的主要前导静音已经存在于模型生成的波形中，而不是浏览器先缓冲了 365ms。

我们只处理每个请求的开头：累积已生成的低振幅前缀，找到超过阈值的位置后，保留起音前 40ms，把更早的部分裁掉。固定文本裁掉约 325ms；浏览器对照那一轮裁掉 353ms。后面的自然停顿不做同样裁剪。

裁剪不会让模型提前算出还没生成的声音。真正的收益来自两部分：模型更快地产生有效帧，以及播放队列不再先播放这段静音。保留前沿余量有助于避免损伤弱起音，但振幅门限仍是启发式，需要用不同首字和音色验证。

## 5. WebSocket 与播放器也属于推理链路

服务端把 LLM delta 同时送到页面和 TTS 队列，文本不是等语音完成才显示。音频元数据和 PCM 二进制包经过同一个 WebSocket，客户端校验请求归属后排入 Web Audio。

播放器维护连续游标，而不是每个包到达就立刻启动一个独立片段：

```javascript
const when = Math.max(cursor, audioContext.currentTime + 0.012);
source.start(when);
cursor = when + buffer.duration;
```

12ms 是本次实现的调度余量，不是通用最优值。停止操作同时清空本地音频、丢弃迟到包、取消远端生成，并释放单会话锁。否则下一次测试可能测到上一轮遗留的音频或排队。

后来添加的九音色选择只改变请求里的 speaker，共用原有流式和 graph 路径。内网 HTTP 访问还暴露了 `crypto.randomUUID()` 不可用的问题；请求关联 ID 增加时间戳加页面内序号的兼容分支。这个 ID 不用于认证，不能把这种回退用于安全 token。

## 测试结果：端到端与固定文本分别看

浏览器测试使用相同问题“请用两句话介绍一下杭州适合散步的地方”，前后返回文字相同：

| 指标 | 优化前 | 优化后 |
| --- | ---: | ---: |
| 首文字 | 697ms | 265ms |
| 首 PCM | 861ms（含静音） | 453ms |
| 预计出声 | 1513ms | 550ms |
| 首文字 → 预计出声 | 816ms | 285ms |
| 生成完成 | 22.123s | 7.216s |
| 音频长度 | 16.80s | 16.45s |
| 播放断流累计 | 4044ms | 0ms |

这里 LLM 的首字也变快了，不能把全部端到端差值归因于 TTS。这是各一轮前后对照，不是 p50/p95。

因此另用固定文本、seed 42 测 TTS：

> 你好，欢迎测试。今天我们测试首字朗读和持续音频生成的速度。

| 指标 | 原版 | 最终版第1轮 | 最终版第2轮 |
| --- | ---: | ---: | ---: |
| 生成耗时 | 8.415s | 2.803s | 2.794s |
| 首有效音频包 | 634ms | 183ms | 189ms |
| 预计起音 | 682ms | 226ms | 231ms |
| 输出音频长度 | 6.640s | 6.315s | 6.315s |

生成速度约提高 3 倍。输出长度减少主要对应开头约 325ms 的裁剪；固定文本最终版的播放模拟仍有约 58ms 短缺口，因此不能用浏览器那轮的 0ms 宣称“任何场景都没有断流”。

## 如何证明没有等后文，以及检查漏读和重复

最直接的方法是故意不给后文。四轮分别先给“你”“你”“我”“请”，后文延迟 2、2、5、2 秒。首有效音频包约在 219、252、218、218ms 到达。

我们只截取**第二份文本到达之前已经收到的音频**，再做 ASR，结果分别为“你”“你”“我”“请”。这样可以避免把收到后文之后才生成的声音误当作首字能力。

最终回归包含 13 个场景（其中一个是等待后文的对照）和 4 份首字截取，共 17 份 ASR 校验：

- 15 份逐字相同。
- 两份分别出现“先→仙”“步→不”的同音字替换。
- 没有 ASR 检出的删除或插入。

另有三轮真实 LLM 流式输出逐字对齐。部署后 `/chat` 两轮完整录音中，一轮逐字相同，一轮为“胜地→圣地”的同音替换，未检出漏读或重复。取消、断开、等待期间取消与断开均能释放会话，同连接取消后复用也通过。

ASR 可能漏掉或误判发音问题，因此这些结果只是验收证据，不等于真人听感评价，更不是任意输入的零错误保证。

## 失败尝试也是结果的一部分

早期加速候选曾产生额外语音。为了稳定收尾，我们试过全 greedy，也试过只在碎片化请求结束后使用确定性尾部；这两种改动又出现了漏读，因此撤回。最终部署保留原采样方式，仅优化执行和解码。

这说明“更快结束”和“完整读完”不是同一个目标。缩短尾音、强制 EOS 或改变采样都可能让延迟指标好看，却破坏内容。优化过程必须同时保存文本、事件和完整音频，不能只看首包时间。

## 下一步该测什么

这次结果支持继续使用当前路径，但还有明确的验证空白：更广的首音素与多语言输入、九音色的完整性回归、不同网络抖动、长文本、并发排队，以及冷启动与 p95 延迟。25 帧上下文和静音阈值也需要更广的音质检查。

最值得保留的方法是：把首包与真实起音分开，把 LLM 延迟与 TTS 耗时分开，用延迟后文验证输入流式，用完整音频验证内容，再决定是否部署。**本次加速把链路推进到了数百毫秒起音，而不是已经实现了低于 100ms 的全链路语音交互。**

*数据说明：本文数字来自 2026-10-21 的单会话实验记录。公开文章与复现目录包含服务及基准源码，不附内部服务地址、会话日志或模型权重；完整依赖快照的全新安装尚未验证，具体复现边界见目录说明。*

复现代码独立进程复测：固定文本生成 2.778s，首有效 PCM 199ms；后文延迟5秒时首有效 PCM 217ms，截取首字ASR为“我”，全文对齐。复用了原安装环境，尚未验证全新依赖安装。详见[机器可读结果](qwen3-tts-streaming-repro/validation-result.json)。
