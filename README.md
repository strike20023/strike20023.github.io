# strike20023.github.io

个人主页、技术博客、自用脚本与公开静态资源，通过 GitHub Pages 发布。

访问 [网站根地址](https://strike20023.github.io/) 会自动跳转到 [个人主页](https://strike20023.github.io/homepage/)。指定路径可直接访问博客、脚本和静态文件。

## 目录

| 目录 | 内容 |
| --- | --- |
| [`homepage/`](homepage/) | 个人主页 HTML 和 CSS |
| [`blogs/`](blogs/README.md) | 技术博客，编辑与发布说明见目录内 README |
| [`files/`](files/) | Surge 配置、规则集、公钥和图标 |
| [`scripts/`](scripts/) | 脚本、Surge 模块和用户脚本 |
| [`tools/quartz/`](tools/quartz/) | 博客构建工具和配置 |

## 配置与静态资源

| 内容 | 公开地址 |
| --- | --- |
| Surge 主配置 | [rule.conf](https://strike20023.github.io/files/rule.conf) |
| Apple 规则集 | [apple.rule](https://strike20023.github.io/files/apple.rule) |
| ChatGPT / OpenAI 规则集 | [chatgpt.rule](https://strike20023.github.io/files/chatgpt.rule) |
| Grok 规则集 | [grok.rule](https://strike20023.github.io/files/grok.rule) |
| SSH 公钥 | [public.key](https://strike20023.github.io/files/public.key) |
| 微信蓝色图标 | [wechat_blue_icon.icns](https://strike20023.github.io/files/wechat_blue_icon.icns) |

## 脚本与模块

| 内容 | 公开地址 |
| --- | --- |
| Hermex 私有 HTTPS Surge 模块 | [hermex_private_https.sgmodule](https://strike20023.github.io/scripts/hermex_private_https.sgmodule) |
| 健身房 Surge 模块 | [gym_check.sgmodule](https://strike20023.github.io/scripts/gym_check.sgmodule) |
| 健身房空位检查 | [gym_check.js](https://strike20023.github.io/scripts/gym_check.js) |
| 健身房 Cookie 提取 | [gym_get_cookie.js](https://strike20023.github.io/scripts/gym_get_cookie.js) |
| iSH 初始化 | [ish_ios_startup.sh](https://strike20023.github.io/scripts/ish_ios_startup.sh) |
| SOCKS5 服务 | [socks5_server.py](https://strike20023.github.io/scripts/socks5_server.py) |
| macOS 微信双开 | [create_a_wechat_clone.sh](https://strike20023.github.io/scripts/create_a_wechat_clone.sh) |
| IELTS 用户脚本 | [ielts_tools.js](https://strike20023.github.io/scripts/ielts_tools.js) |

## 发布

推送到 `main` 后，[GitHub Actions](.github/workflows/pages.yml) 自动构建、检查并发布网站。个人主页编辑 `homepage/index.html` 和 `homepage/styles.css`；博客维护方法见 [`blogs/README.md`](blogs/README.md)。

生成文件、依赖、缓存和本地环境文件不提交到仓库。
