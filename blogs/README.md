# Blogs

[博客网站](https://strike20023.github.io/blogs/) · [项目索引](index.md)

博客使用 Quartz 发布，按项目组织 Markdown 文章、附件和复现资源。

## 本地编辑

在 Obsidian 中选择“打开本地仓库”，打开仓库内的 `blogs` 文件夹。每个项目使用独立目录，以 `index.md` 作为入口。

当前项目：[Qwen3-TTS 流式链路优化](qwen3-tts-streaming/index.md)，包含[中文文章](qwen3-tts-streaming/optimization.zh.md)、[英文文章](qwen3-tts-streaming/optimization.en.md)和[复现指南](qwen3-tts-streaming/repro/README.md)。

新增文章可在文件开头设置 `title`、`date`、`description` 和 `tags`。内部链接使用包含路径的相对链接，附件放在所属项目目录中。

## 预览与发布

需要 Node.js 22 或更高版本、npm 10.9.2 或更高版本，以及 Git。首次使用时，在仓库根目录运行：

```sh
npm ci
npm run setup
```

构建、检查并启动预览：

```sh
npm run build
npm run check
npm run preview
```

博客预览地址为 `http://127.0.0.1:8080/blogs/`。修改内容后重新运行 `npm run build` 并刷新页面。预览服务器的根地址默认跳转到个人主页。

推送到 `main` 后，GitHub Actions 自动构建并发布到 `/blogs/`。

## 构建配置

- [页面与插件配置](../tools/quartz/quartz.config.yaml)
- [Quartz 版本](../tools/quartz/upstream.json)
- [旧公开文件路径映射](../tools/quartz/legacy-paths.json)

构建产物保存在 `.site/`；旧博客的 Markdown、HTML 和复现文件地址由构建流程生成兼容文件。
