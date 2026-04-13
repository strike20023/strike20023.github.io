# 脚本小子

这个仓库通过 GitHub Pages 托管自用脚本、规则配置和公开静态文件。

## 目录结构

当前只保留两个主要目录：

- `files/`：公开静态文件和配置文件，例如规则、公钥、图标。
- `scripts/`：可直接远程引用或执行的脚本、模块、用户脚本。

根目录只放仓库说明和配置文件，例如 `README.md`、`.gitignore`。

## 公开地址

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

- 静态资源、规则、公钥放进 `files/`。
- 脚本、模块、用户脚本放进 `scripts/`。
- 新增公开文件后，同步在本 README 的「公开地址」中登记。
- 不提交系统生成物、缓存、临时文件；这些由 `.gitignore` 处理。
