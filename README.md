# strike20023.github.io

这个仓库通过 GitHub Pages 托管个人主页、自用脚本、规则配置和公开静态文件。

## 目录结构

当前主要目录：

- `homepage/`：个人主页 Markdown。
- `blogs/`：按项目组织的 Markdown 博客，可在 Obsidian 中打开。
- `tools/quartz/`：Quartz 配置、构建与公开地址兼容规则。
- `files/`：公开静态文件和配置文件，例如规则、公钥、图标。
- `scripts/`：可直接远程引用或执行的脚本、模块、用户脚本。

根目录只放仓库说明和配置文件，例如 `README.md`、`.gitignore`。

## 公开地址

### homepage

| 用途 | 地址 |
| --- | --- |
| 个人主页 | `https://strike20023.github.io/homepage/` |

### blogs

| 用途 | 地址 |
| --- | --- |
| 博客目录 | [博客网站](https://strike20023.github.io/blogs/) |
| Qwen3-TTS 流式优化（中文 Markdown） | [中文](blogs/qwen3-tts-streaming/optimization.zh.md) |
| Qwen3-TTS streaming optimization (English Markdown) | [English](blogs/qwen3-tts-streaming/optimization.en.md) |

### files

| 用途 | 地址 |
| --- | --- |
| Surge 规则 | `https://strike20023.github.io/files/rule.conf` |
| Apple 规则 | `https://strike20023.github.io/files/apple.rule` |
| SSH 公钥 | `https://strike20023.github.io/files/public.key` |
| 微信蓝色图标 | `https://strike20023.github.io/files/wechat_blue_icon.icns` |

### scripts

| 用途 | 地址 |
| --- | --- |
| Hermex 私有 HTTPS Surge 模块 | `https://strike20023.github.io/scripts/hermex_private_https.sgmodule` |
| 健身房 Surge 模块 | `https://strike20023.github.io/scripts/gym_check.sgmodule` |
| 健身房空位检查脚本 | `https://strike20023.github.io/scripts/gym_check.js` |
| 健身房 Cookie 抓取脚本 | `https://strike20023.github.io/scripts/gym_get_cookie.js` |
| iSH 初始化脚本 | `https://strike20023.github.io/scripts/ish_ios_startup.sh` |
| SOCKS5 服务脚本 | `https://strike20023.github.io/scripts/socks5_server.py` |
| macOS 微信双开脚本 | `https://strike20023.github.io/scripts/create_a_wechat_clone.sh` |
| IELTS 用户脚本 | `https://strike20023.github.io/scripts/ielts_tools.js` |

## 使用示例

### iSH 初始化

```sh
wget -qO- https://strike20023.github.io/scripts/ish_ios_startup.sh | sh
```

### macOS 微信双开

```sh
bash <(curl -fsSL https://strike20023.github.io/scripts/create_a_wechat_clone.sh)
```

## 维护约定

- 个人主页相关文件放进 `homepage/`。
- 静态资源、规则、公钥放进 `files/`。
- 脚本、模块、用户脚本放进 `scripts/`。
- 新增公开文件后，同步在本 README 的「公开地址」中登记。
- 不提交系统生成物、缓存、临时文件；这些由 `.gitignore` 处理。

## 本地编辑与发布

网站统一使用 Quartz。个人主页编辑 `homepage/index.md`，博客编辑 `blogs/` 下对应项目的 Markdown。

需要 Node.js 22 或更高版本、npm 10.9.2 或更高版本和 Git。

```sh
npm ci
npm run setup
npm run build
npm run check
npm run preview
```

预览地址为 `http://127.0.0.1:8080/`。修改内容后重新运行 `npm run build` 并刷新页面。推送到 `main` 后，GitHub Actions 自动构建并发布网站。

在 Obsidian 中选择“打开本地仓库”，打开 `blogs` 目录即可编辑博客。

Quartz 版本固定在 `tools/quartz/upstream.json`；页面配置位于 `tools/quartz/quartz.config.yaml`。构建产物位于 `.site/`。旧公开博客路径在 `tools/quartz/legacy-paths.json` 中维护，由构建流程生成。
