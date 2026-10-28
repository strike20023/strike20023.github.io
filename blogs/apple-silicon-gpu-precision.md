---
title: "Mac 的 Apple Silicon GPU 算力：全型号、浮点精度与低比特矩阵实测"
description: "从 M1 到 M6，核对 Mac GPU 配置、FP32/FP16/BF16、FP8/MXFP4 与 INT8 的计算路径、公开测试和证据边界。"
date: 2026-10-28
tags:
  - hardware/apple-silicon
  - machine-learning
  - benchmarks
---

# Mac 的 Apple Silicon GPU 算力：全型号、浮点精度与低比特矩阵实测

一台 Mac 有多少 TFLOPS，必须先说明**哪颗芯片、多少 GPU 核心、什么运算、什么输入与累加精度，以及是否使用矩阵加速单元**。GPU 的普通浮点指令、矩阵乘法和 SoC 上独立的 Neural Engine，不能用一个“AI 算力”数字混在一起比较。

本文以 **2026 年 10 月 28 日**为资料截止日，覆盖已经发布的商用 Mac 芯片与 GPU 核心配置，包括 M1–M6、相应 Pro / Max / Ultra，以及 MacBook Neo 的 A18 Pro。同一芯片、同一 GPU 核数的不同 CPU、内存、SSD 配置不另列为一种 GPU。文中的实测均来自公开报告，未在本文重新运行。

最有用的判断是：M1–M4 的低精度性能主要取决于 shader、矩阵原语和编译器；从 M5 起，GPU 内增加 Neural Accelerators，必须单独测量 TensorOps 路径。**能加载 4-bit 权重，不等于拥有 FP4 峰值；支持 BF16 类型，也不等于 BF16 比 FP32 快两倍。**[^apple-nax]

## 1. 先统一“算力”的口径

- **理论峰值（T）**：由执行宽度、频率和每周期操作数计算，是理想上限。
- **实测（M）**：某个程序在指定机器上的吞吐。短时最佳值、稳态中位数和端到端模型速度是不同指标。
- **估算（E）**：由已知配置推算，必须写出假设。
- **未核实（—）**：本次检索没有找到足以填入该格的报告；不表示硬件性能为零。

浮点使用 TFLOPS，整数使用 TOPS，均按十进制 `10^12` 计。一次 FMA（乘加）计为 2 次运算；对 `M×K` 与 `K×N` 的稠密矩阵乘法，常用计算量为 `2MNK`。不额外套用稀疏倍率。

普通 SIMD 浮点峰值可以近似写为：

```text
TFLOPS = GPU 核数 × 每核每周期 FLOP × GPU 频率(GHz) / 1000
```

这个公式不适合直接估算不同精度的专用矩阵单元，也不能把 GPU 核心数与 NVIDIA CUDA core 数直接比较。

## 2. 全型号与 GPU 核心配置

表中斜线两侧一一对应。M1/M2 的 FP32 与 FP16 数字采用 Philip Turner 的 GPU 微架构数据：完整配置为报告所列理论值，裁剪配置按相同频率与吞吐比例估算；M2 Ultra 也是按 M2 系列每核吞吐估算。它们**不是 GEMM 实测**。[^turner]

| 芯片 | 商用 Mac GPU 核数 | FP32 普通计算 TFLOPS | FP16 普通计算 TFLOPS | 其他精度的证据入口 |
| --- | --- | --- | --- | --- |
| M1 | 7 / 8 | E 2.29 / T 2.62 | E 2.29 / T 2.62 | 下文标量与 MPS 报告 |
| M1 Pro | 14 / 16 | E 4.64 / T 5.31 | E 4.64 / T 5.31 | 14 核 BF16 / FP16 实测 |
| M1 Max | 24 / 32 | E 7.96 / T 10.62 | E 7.96 / T 10.62 | 缺少本文口径的完整精度实测 |
| M1 Ultra | 48 / 64 | E 15.93 / T 21.23 | E 15.93 / T 21.23 | 缺少完整精度实测 |
| M2 | 8 / 10 | E 2.86 / T 3.58 | E 2.86 / T 3.58 | MPS FP32 实测 |
| M2 Pro | 16 / 19 | E 5.73 / T 6.80 | E 5.73 / T 6.80 | 缺少完整精度实测 |
| M2 Max | 30 / 38 | E 10.74 / T 13.60 | E 10.74 / T 13.60 | 两种配置均有标量 BF16 实测 |
| M2 Ultra | 60 / 76 | E 21.47 / E 27.20 | E 21.47 / E 27.20 | 缺少完整精度实测 |
| M3 | 8 / 10 | — | — | MPS FP32 实测 |
| M3 Pro | 14 / 18 | — | — | 14 核标量三精度实测 |
| M3 Max | 30 / 40 | — | — | 缺少本文口径的完整精度实测 |
| M3 Ultra | 60 / 80 | — | — | 有 BF16 扫描日志，但日志未注明 GPU 核数 |
| M4 | 8 / 10 | — | — | 10 核标量三精度与 MPS FP32 实测 |
| M4 Pro | 16 / 20 | — | — | 20 核标量与 MLX GEMM 实测 |
| M4 Max | 32 / 40 | — | — | 有 BF16/FP16 性能声明，测试元数据不足 |
| M5 | 8 / 10 | — | — | 10 核 TensorOps 多精度实测 |
| M5 Pro | 16 / 20 | — | — | 20 核 TensorOps 多精度实测 |
| M5 Max | 32 / 40 | — | — | 40 核 TensorOps 多精度实测 |
| M5 Ultra | 64 / 80 | — | — | 有 GPU Neural Accelerators；所引矩阵项目尚无实测 |
| M6 | 10 / 12 | — | — | 12 核 TensorOps 多精度实测；10 核配置刚随 iMac 发布 |
| A18 Pro（MacBook Neo） | 5 | — | — | 不把 iPhone 的 6 核结果移植到此配置 |

核心配置依据 Apple 的产品规格与发布资料核对。M1/M2 高阶配置见历代 MacBook Pro 与 Mac Studio 规格；M3 Pro/Max 为 14/18 与 30/40 核，M3 Ultra 为 60/80 核；M4 Pro/Max 为 16/20 与 32/40 核。[^sku-m1][^sku-m1studio][^sku-m2][^sku-m2studio][^sku-m3][^sku-m3studio][^sku-m4]

M5 Pro/Max 为 16/20 与 32/40 核，M5 Ultra 为 64/80 核。M6 已经进入 Mac mini，新发布的 iMac 增加了 10 核 GPU 版本；MacBook Neo 的 A18 Pro 为 5 核 GPU。[^sku-m5][^sku-m5air][^sku-m5studio][^m6][^imac-m6][^neo]

这里没有把未发布的“M4 Ultra”“M6 Pro/Max/Ultra”当作商品型号。2020 年开发者过渡套件 DTK 的 A12Z 不属于零售 Mac；若把它也纳入硬件历史，其 8 核 GPU 的报告理论值约为 FP32 1.155、FP16 2.310 TFLOPS，同样不能替代正式 Mac 的测量。[^turner]

后几代留空的原因是：公开资料常把估算时钟、shader 峰值、TensorOps 吞吐和实测 GEMM 混写。这里把可核验的实测放到各自表格，不用一个未经核实的倍数填满整张表。

## 3. 各精度究竟意味着什么

| 格式 | 数据含义 | 在 Mac 上应该核实的事项 |
| --- | --- | --- |
| FP64 | 64 位浮点，常用于高精度科学计算 | 所引 M 系列研究指出 GPU 缺少原生 FP64；软件仿真或 CPU BLAS 不能记作 GPU FP64 峰值 |
| FP32 | 32 位浮点 | 分清严格精度与允许降低中间精度的矩阵路径 |
| FP16 | 16 位浮点，5 位指数、10 位尾数 | 输入、累加、输出是否都为 FP16；输入 FP16、累加 FP32 很常见 |
| BF16 | 16 位浮点，8 位指数、7 位尾数 | 动态范围接近 FP32，尾数更短；类型支持、原生指令和具体矩阵实现是三件事 |
| TF32 / relaxed FP32 | 通常以 FP32 存储、在乘法中降低有效精度 | 必须标记数学语义，不能作为严格 FP32 比较基准 |
| FP8 | E4M3、E5M2 等 8 位浮点编码 | 两种编码的结果不能互换；还要检查缩放与累加精度 |
| FP4 | 常见 E2M1 的 4 位浮点编码 | 单独编码与带块缩放的 MXFP4 是不同路径 |
| MXFP4 / MXFP8 | 小位宽元素加共享块缩放 | 要同时计算打包、缩放、反量化及矩阵运算的成本 |
| INT8 / INT4 | 整数，并非浮点类型 | W8A8、W4A16、INT8×INT4 不是同一种运算；整数乘法通常要说明累加类型 |

OCP 的 MXFP4 使用 E2M1 元素，每 32 个值共享一个 E8M0 缩放因子。仅计元素与缩放，平均占用为 `4+8/32=4.25` bit/value，并非恰好 4 bit；对齐和其他元数据还会增加实际空间。[^ocp]

Apple 的 Metal 功能表把 `bfloat` 类型支持与 GPU family 联系起来，但并不提供各芯片的 BF16 TFLOPS；功能表不能直接当性能表。[^metal-features] FP64 的限制见 HPC 测量论文。[^hpc]

## 4. M1–M4：同一个精度也会有完全不同的测量结果

### 4.1 标量算术微基准

Deepsweet 的 Swift/Metal 程序报告以下结果，单位由 GFLOPS 换算成 TFLOPS，保留三位小数。这是该程序的吞吐，不是每颗 GPU 的硬件峰值。[^scalar]

| GPU | FP32（M） | FP16（M） | BF16（M） |
| --- | ---: | ---: | ---: |
| M1 Pro，14 核 | 0.885 | 1.467 | 0.884 |
| M2 Max，30 核 | 2.056 | 3.399 | 2.055 |
| M2 Max，38 核 | 2.602 | 4.253 | 2.600 |
| M3 Pro，14 核 | 1.857 | 1.725 | 1.686 |
| M4，10 核 | 1.559 | 1.434 | 1.404 |
| M4 Pro，20 核 | 3.122 | 2.869 | 2.805 |

M1 Pro 和 M2 Max 的 BF16 几乎与 FP32 相同；M3 Pro、M4 系列的 BF16 更接近 FP16。这支持“计算路径发生变化”的判断，但**仅凭相近耗时，不能独立证明编译器用了哪条硬件指令**。作者把它解释为早期芯片上经 FP32 仿真、后期芯片上原生 BF16；要确认微架构，还需要反汇编或指令级证据。CPU 的 `hw.optional.arm.FEAT_BF16` 也不能回答 GPU 的问题。[^scalar]

### 4.2 矩阵乘法：比标量程序更接近训练和 prefill

《Apple vs. Oranges》的 MPS FP32 矩阵测试报告 M1、M2、M3、M4 分别达到约 **1.36、2.24、2.47、2.90 TFLOPS**。这些是作者实验设备和矩阵尺寸扫描下的最佳值，不代表整个同代系列。论文同时展示了手写 kernel 与 MPS 之间的巨大差距：算法、分块和库实现足以改变“这颗芯片有多快”的答案。[^hpc]

另一个带代码的 MLX 测试使用 **M4 Pro 20 核 GPU、48GB 内存**：[^mlx-m4pro]

| 方阵维度 | FP32 TFLOPS（M） | FP16 TFLOPS（M） |
| --- | ---: | ---: |
| 2048 | 3.872 | 6.769 |
| 4096 | 6.528 | 7.349 |
| 8192 | 6.262 | 7.447 |

因此，同为 M4 Pro，不能把上一表的 2.869 FP16 TFLOPS 当作 MLX 大矩阵的上限，也不能把这里的 7.447 当作任意操作都可达到的速度。

还有两条值得保留、但不宜升级为规格的数据：

- **M3 Ultra BF16**：Ivan Fioravanti 公布的 PyTorch 2.9.0 / MPS 原始日志扫描了 3375 种形状，最佳均值 25.6 TFLOPS、最佳中位数与最大值 25.7 TFLOPS。日志没有明确 GPU 核数，故不能把它分别填入 60 核和 80 核两种配置。[^m3ultra-log]
- **M4 Max BF16/FP16**：MetalMarlin README 声称约 14.8 TFLOPS，并附测试脚本入口；该段未提供完整核心配置、形状和运行环境，因此这里只作为进一步复现线索。[^marlin]

## 5. M5 与 M6：TensorOps 需要独立列账

Apple 明确区分 GPU 内的 Neural Accelerators 与独立的 Neural Engine。TensorOps 在 M5 上利用 GPU 矩阵硬件；同一 API 在较早 GPU 上可以退回优化过的 shader 实现。API 能运行，并不意味着硬件相同。Apple 还分别在系统 26.1、26.3、26.4 扩展了 BF16、cooperative tensor 输入、4/8 位整数张量支持。[^apple-nax]

Precisit 的公开测试项目提供逐次记录、程序哈希与校验结果。下面摘取 2026-10-14 的报告，浮点单位为 TFLOPS，整数为 TOPS；输入与输出格式写在行名中。[^matrix]

| 矩阵路径 | M5 Air 10 核 | M5 Pro 20 核 | M5 Max 40 核 | M6 12 核 |
| --- | ---: | ---: | ---: | ---: |
| 严格 FP32×FP32→FP32 | 3.646 | 7.565 | 14.526 | 4.183 |
| FP16×FP16→FP32 | 12.961 | 28.392 ⚠ | 51.727 | 13.933 |
| BF16×BF16→FP32 | 12.453 | 32.010 | 62.587 | 13.234 |
| FP8 E4M3×E4M3→FP32 | 14.056 | 29.438 | 51.162 ⚠ | 29.044 ⚠ |
| FP4×FP4→FP32 | 12.042 | 26.300 | 48.070 ⚠ | 14.964 |
| MXFP4×FP4→FP32（源项目 `mx_fp4*fp4`） | 9.231 | 20.798 | 37.953 | 10.626 |
| INT8×INT8→INT32 | 24.580 | 60.423 | 115.094 | 31.252 |
| INT8×INT4→INT32 | 21.494 | 50.127 | 94.360 | 26.958 |

⚠ 表示源报告标记采样最大/最小时间相差超过 2 倍。该表是**短时、最佳 tile/样本**结果，标准形状为 M×K×N = 2048×4096×4096；不是持续运行的保证值，也不是模型 tokens/s。[^matrix][^methods]

两个容易误读的地方：

1. BF16 与 FP16 行来自不同 sweep，不能拿 62.587÷51.727 得出“M5 Max 的 BF16 比 FP16 快 21%”。同一份整数 sweep 的 FP16 基线是 62.535，BF16 实际与它接近；FP16 行选用的是浮点 sweep 的基线。[^matrix]
2. 严格 FP32 与 relaxed FP32 不是相同精度条件。源项目的默认非严格 FP32 数字更高，不能替换表中的严格 FP32 来宣传硬件提升。[^methods]

这组数据没有显示 FP4 相对 FP16 的倍增吞吐，MXFP4 路径也没有因为存储位宽更小就变快。M6 的 E4M3 路径则值得单独研究，但带波动标记的结果需要复测；不能把结论推广到 E5M2、MXFP8 或 M5 Ultra。[^matrix]

另一份 M5 10 核、24GB 的独立微架构报告测到约 **15.4 FP16 TFLOPS** 的 GPU Neural Accelerator 吞吐与 **120.4 GB/s** 的实际内存带宽。它与上表的差异提醒我们：矩阵形状、内核、计时和机器状态都属于结果的一部分。[^dwijen]

## 6. BF16、MXFP4、INT8 应该怎么选

**BF16 用于需要 FP32 指数范围的模型。** FP16 与 BF16 同为 2 字节，BF16 不会凭格式本身减少一半内存；它用较少尾数换更大的指数范围。M1/M2 尤其应实测 BF16 与 FP16 的差别。把原始 BF16 模型改成 FP16 时，还必须验证溢出、NaN 和模型质量。

**MXFP4 首先是一种存储与传输选择。** 若 kernel 先解包、缩放，再交给 FP16/BF16 矩阵路径，那么真正耗时包含反量化；W4A16 也不能称为原生 W4A4。只有测到输入格式、缩放语义和指令路径，才能讨论“MXFP4 算力”。OCP 格式定义并不规定某一颗 GPU 必须怎样执行它。[^ocp]

**INT8 必须看两边输入。** INT8×INT8→INT32 与 FP16×INT8→FP32 的吞吐不同。权重为 8 位也不保证激活为 8 位，更不保证使用整数矩阵单元。量化策略还需考虑校准、尺度粒度和精度损失。

**FP64 工作负载要另做平台判断。** 需要严格双精度的数值算法，不能用 GPU FP16 或 ANE TOPS 代替评估；CPU、软件仿真以及不同硬件平台应分别测试。[^hpc]

## 7. 为什么 TFLOPS 上升，生成 token 却未必更快

一个粗略上限是 Roofline 关系：

```text
可达 FLOPS ≤ min(计算吞吐上限, 实际内存带宽 × 算术强度)
```

Prefill 或较大 batch 的矩阵乘法能重复利用权重，更容易受计算能力限制；单请求逐 token decode 则常需要反复读取大量权重。比如，每步实际搬运 20GB 数据、有效带宽 400GB/s，单看权重读取就需要约 50ms，对应约 20 token/s 的理想上限；注意力、KV cache、调度与其他运算还会继续增加时间。这是示意计算，不是某台 Mac 的测试结果。

因此判断 Mac 的本地模型性能，应同时看：GPU 具体核心配置、内存容量与有效带宽、prefill 和 decode 分项结果、模型精度、batch 与上下文长度。M5 Ultra 的大内存和 GPU 矩阵硬件是不同维度的优势，不能只把它们折合为一个 TFLOPS。[^m6]

## 8. 如何复测并补齐空白

读者可以从三类公开工具开始：Philip Turner 的指令微基准、Deepsweet 的标量精度程序，以及 Precisit 的 TensorOps 矩阵探针。选择与实际应用相同的 API 路径，再补上 MLX 或 MPS GEMM 测试。[^turner][^scalar][^methods]

每次报告至少记录：

- 芯片全名、GPU 核数、内存、机型、系统与 Xcode/Metal/框架版本。
- 输入、累加、输出类型；严格/relaxed 精度；块缩放、打包和稀疏设置。
- M/N/K、batch、转置、布局和 tile，是否包含反量化与 CPU/GPU 同步。
- 预热次数、重复次数、最佳值与中位数、持续运行结果、供电与低功耗状态。
- 与高精度参考结果的误差、NaN/Inf 检查，以及代码提交版本。

对延迟执行的框架，计时前后必须等待 GPU 真正完成；仅测 Python 函数返回时间会产生虚高结果。先验证输出，再比较速度。缺少原始环境与计时口径的“某芯片 XX TFLOPS”，适合作为线索，不能当成跨型号排名。

## 参考资料

[^turner]: Philip Turner，Apple GPU microarchitecture / Metal Benchmarks，含 M1/M2 普通指令吞吐、频率及开源测试。https://github.com/philipturner/metal-benchmarks
[^apple-nax]: Apple Developer，Accelerate your machine learning workloads with the M5 and A19 GPUs，GPU Neural Accelerators、TensorOps 与系统版本要求。https://developer.apple.com/videos/play/tech-talks/111432/
[^metal-features]: Apple，Metal Feature Set Tables（查阅版本标注 2026-05-21；不覆盖随后所有新产品）。https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf
[^sku-m1]: Apple，MacBook Pro 14-inch 2021 技术规格。https://support.apple.com/en-us/111902
[^sku-m1studio]: Apple，Mac Studio 2022 技术规格。https://support.apple.com/en-us/111900
[^sku-m2]: Apple，MacBook Pro 14-inch 2023 技术规格。https://support.apple.com/en-us/111340
[^sku-m2studio]: Apple，Mac Studio 2023 技术规格。https://support.apple.com/en-us/111835
[^sku-m3]: Apple，MacBook Pro M3 Pro / M3 Max 技术规格。https://support.apple.com/en-us/117736
[^sku-m3studio]: Apple，Mac Studio 2025 技术规格。https://support.apple.com/en-us/122211
[^sku-m4]: Apple，MacBook Pro M4 Pro / M4 Max 技术规格。https://support.apple.com/en-us/121553
[^sku-m5]: Apple，MacBook Pro M5 Pro / M5 Max 技术规格。https://support.apple.com/en-us/126318
[^sku-m5air]: Apple，MacBook Air 技术规格。https://www.apple.com/macbook-air/specs/
[^sku-m5studio]: Apple，Mac Studio M5 Max / M5 Ultra 技术规格。https://www.apple.com/au/mac-studio/specs/
[^m6]: Apple，M6 与 M5 Ultra 发布资料，2026-08-25。https://www.apple.com/newsroom/2026/08/apple-introduces-m6-and-m5-ultra-for-a-big-leap-in-performance-and-ai-compute/
[^imac-m6]: Apple，iMac 技术规格，含 M6 10/12 核 GPU。https://www.apple.com/imac/specs/
[^neo]: Apple，MacBook Neo 技术规格，A18 Pro 5 核 GPU。https://www.apple.com/au/macbook-neo/specs/
[^ocp]: Open Compute Project，Microscaling Formats（MX）Specification v1.0。https://www.opencompute.org/documents/ocp-microscaling-formats-mx-v1-0-spec-final-pdf
[^hpc]: Hübner 等，Apple vs. Oranges: Evaluating the Apple Silicon M-Series SoCs for HPC Performance and Efficiency，arXiv:2502.05317v1。https://arxiv.org/html/2502.05317v1
[^scalar]: Deepsweet，Metal FP32 Vs BF16 Vs FP16 benchmark，固定提交 e9214ef。https://github.com/deepsweet/metal-fp32-bf16-fp16/tree/e9214ef360bba312f2c64e54638330d962cc1f1c
[^mlx-m4pro]: Jialiang Fan，Mac TFLOPS Benchmark，M4 Pro 20 核 GPU 的 MLX GEMM 数据。https://github.com/JialiangFan/mac_tflops
[^m3ultra-log]: Ivan Fioravanti，M3 Ultra BF16 原始扫描日志，2025-10-19。https://gist.github.com/ivanfioravanti/b1bb415acaeb8d7a9c8e2beb7bfc4e8c
[^marlin]: MetalMarlin，性能声明及 `bench_dtype_perf.py` 入口。https://github.com/Infatoshi/MetalMarlin
[^matrix]: Precisit，Apple matrix capabilities，固定提交 f1464e4 的能力与实测表；“—”为未测，不是零性能。https://github.com/precisit/apple-matrix-capabilities/blob/f1464e4ece4a07774728d392677bc83b9efc4a84/matrix/MATRIX.md
[^methods]: Precisit，测试方法、计时差异与精度设置。https://github.com/precisit/apple-matrix-capabilities/blob/f1464e4ece4a07774728d392677bc83b9efc4a84/METHODS.md
[^dwijen]: Dwijen，The M5 Tensor Path，M5 10 核 24GB 的独立微架构与带宽测试。https://dwijen.com/experiments/apple-silicon-gpu-kernels-architecture/
