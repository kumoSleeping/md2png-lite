# md2png-lite

[English](README.md) · [中文](README_zh.md)

纯 Python 的 Markdown 渲染器，输出 PNG 图片。

## 目标

- 不依赖浏览器
- 不依赖 WeasyPrint
- 支持跨平台 `pip install`
- 主题可配置
- 支持 Markdown、代码高亮和基础公式

## 渲染思路

- 用 `markdown-it-py` + `dollarmath` 解析 Markdown，映射到一套小型文档模型，再直接在 Pillow 画布上排版标题、段落、表格、引用、图片和代码块。不走浏览器，也不走 HTML 截图。
- 字体选择不是固定一套字体，而是按字形覆盖率挑选。它会自动发现系统字体和自定义字体，用 `matplotlib.ft2font` 评估覆盖率，先为正文、标题、代码挑主字体，再按文本片段对 CJK 和缺字做回退。
- 现在有两条清晰分开的字体路线：默认安装只走本机系统字体；可选的 `NotoSans` extra 会在首次渲染时把一套 curated Noto 字体同步到用户缓存目录，再在渲染时优先命中这套字体。
- 公式通过 `matplotlib.mathtext` 渲染成透明位图，并做一层轻量 LaTeX 清洗；遇到不支持的语法时，再退化成可读文本。
- 代码高亮由 `Pygments` 负责词法切分，换行和绘制则由渲染器自己完成，因此代码块不依赖浏览器 CSS/JS。

## 安装

```bash
pip install md2png-lite

# 本地开发
uv sync
```

系统字体路线：

```bash
pip install md2png-lite
```

Noto 路线：

```bash
pip install 'md2png-lite[NotoSans]'
```

`NotoSans` extra 不会把字体直接塞进 wheel，而是只安装同步依赖，并在首次使用时把 curated Noto 字体包同步到本地缓存。

## CLI

```bash
uv run md2png-lite input.md -o output.png --theme paper
```

调用时可以显式选择字体路线：

```bash
uv run md2png-lite input.md -o output.png --font-pack system
uv run md2png-lite input.md -o output.png --font-pack noto
```

显式加载自定义字体：

```bash
uv run md2png-lite input.md -o output.png \
  --font-path ./fonts/NotoSansCJKsc-Regular.otf \
  --font-dir ./fonts
```

## 压测

```bash
python3 scripts/benchmark_examples.py --repeat 3 --keep
```

这会渲染仓库自带的压力样例，并输出耗时和结果尺寸。

## 可视化检查样例

渲染更适合人工检查的小样例：

```bash
python3 scripts/render_examples.py
```

也可以传自定义 glob：

```bash
python3 scripts/render_examples.py --pattern 'sample_*.md'
```

## Python

```python
from md2png_lite import render_markdown_image

payload = render_markdown_image("# Hello\n\n```python\nprint('hi')\n```")
```

也可以在单次调用里明确指定：

```python
payload = render_markdown_image(markdown, font_pack="system")
payload = render_markdown_image(markdown, font_pack="noto")
```

返回值格式：

```python
{
    "ok": True,
    "renderer": "md2png-lite",
    "mime_type": "image/png",
    "base64": "...",
}
```

## 支持的语法

- 标题
- 段落
- 无序列表 / 有序列表
- 引用块
- 分割线
- 围栏代码块
- 行内代码
- 表格
- 链接 / 斜体 / 粗体 / 删除线
- 通过 `matplotlib.mathtext` 支持行内和块级公式
- 本地 / `data:` / 远程图片

## 主题

- `paper`：当前这套暖色阅读风格；兼容别名 `阅读器` 仍然可用
- `github-light`：GitHub 风格白天主题
- `github-dark`：GitHub 风格暗色主题
- `solarized-light`：经典 Solarized Light
- `graphite`：现有的深色编辑感主题

## 字体发现

- 自动发现 macOS / Windows / Linux 系统字体
- 支持两条互不干扰的字体路线：`system` 和同步缓存的 `noto`
- 按文本片段选择字体，而不是强制全局单字体
- 优先选择支持 CJK 的字体来处理中文 / 日文 / 韩文
- `font_pack="system"` 时只走平台字体
- `font_pack="noto"` 时会同步 curated Noto 字体到本地缓存并优先使用
- 支持通过 CLI 注入自定义字体：`--font-path`、`--font-dir`
- 支持通过 CLI 选择字体路线：`--font-pack auto|system|noto`
- 支持通过 Provider 配置注入：`md2png_lite.font_paths`、`md2png_lite.font_dirs`、`md2png_lite.font_pack`
- 支持通过环境变量注入：`MD2PNG_LITE_FONT_PATHS`、`MD2PNG_LITE_FONT_DIRS`、`MD2PNG_LITE_FONT_PACK`

同步 Noto 字体许可证说明：

- `licenses/NOTO_CJK_LICENSE.txt`

## 边界

- 公式能力遵循 `matplotlib.mathtext`，不是完整 LaTeX
- HTML block 会按普通文本处理
- 深层嵌套列表和复杂表格可以渲染，但整体布局目标是稳定图片输出，不追求浏览器级像素一致
