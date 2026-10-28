# Blogs

[博客网站](https://strike20023.github.io/blogs/) · [项目索引](index.md)

在 Obsidian 中选择“打开本地仓库”，打开当前 `blogs` 文件夹。每个项目使用一个独立目录，入口为 `index.md`，文章和附件放在项目目录内。

## Qwen3-TTS

[项目概览](qwen3-tts-streaming/index.md) · [中文](qwen3-tts-streaming/optimization.zh.md) · [English](qwen3-tts-streaming/optimization.en.md) · [复现指南](qwen3-tts-streaming/repro/README.md)

## 发布

在仓库根目录运行 `npm ci`、`npm run setup`、`npm run build`。本地预览运行 `npm run preview`，访问终端显示的地址。推送到 `main` 后由 GitHub Actions 发布。

新增文章使用 Markdown；可在文件开头设置 `title`、`date`、`description` 和 `tags`。内部链接优先使用包含路径的相对链接，附件保存在所属项目目录。
