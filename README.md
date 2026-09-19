# Fewreader

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](Dockerfile)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](#)
[![Demo](https://img.shields.io/badge/demo-read.fewlosophy.com-blueviolet)](https://read.fewlosophy.com)

[English](#fewreader) | [简体中文](#简体中文) | [繁體中文](#繁體中文)

A minimal, self-hosted reading app for your `.md` and `.txt` files. No accounts, no cloud, no noise — just your content in a clean browser interface.

**Live Demo**: [read.fewlosophy.com](https://read.fewlosophy.com)

> 💡 **Note**: This project was 100% vibe coded from start to finish.

## Get Started (Docker)

The fastest way is with Docker Compose:

```bash
docker compose up -d
```

Or if you prefer to build it yourself:

```bash
docker build -t fewreader .
docker run -d -p 8000:8000 -v $(pwd)/content:/app/content:ro --name fewreader fewreader
```

Once it's running, open **http://localhost:8000** and you're good to go.

## Running Locally (Python)

```bash
# Install dependencies
pip install -r requirements.txt

# Start the dev server
uvicorn app.main:app --reload --port 8000
```

## Adding Your Content

Drop any `.md` or `.txt` files into the `content/` folder. Sub-folders automatically become categories in the sidebar — no configuration required:

```
content/
├── fiction/
│   └── my_story.txt
├── notes/
│   └── ideas.md
└── welcome.md
```

Save a file and it shows up immediately. No restart, no fuss.

## Configuration

There's not much to tweak, but here's what you can change:

| Variable | Default | What it does |
|---|---|---|
| `CONTENT_DIR` | `content` | Where your files live. Legacy `BOOKS_DIR` also works. |
| `APP_TITLE` | `Fewreader` | The title shown in the nav bar. |

## Architecture

See [fewreader-arch.md](fewreader-arch.md) for a technical overview of the service layers and routing architecture.

## Built With

- **FastAPI** — handles routing
- **Jinja2** — renders the templates
- **python-markdown** — converts Markdown to HTML
- **Tailwind CSS** — keeps everything looking clean

## Local Run and Test Instructions

1. Install dependencies: `pip install -r requirements.txt -r requirements-dev.txt`
2. Run tests: `python -m pytest tests`
3. Start the dev server: `uvicorn app.main:app --reload --port 8000`

## License

[MIT](LICENSE) — do whatever you like with it.

---

## 简体中文

一个轻量的自托管阅读器，用来在浏览器里读 `.md` 和 `.txt` 文件。没有账号，没有云服务，没有多余的东西——只有你的内容，干净呈现。

**在线演示**：[read.fewlosophy.com](https://read.fewlosophy.com)

> 💡 **注**：本项目全程 100% vibe coding 打造。

### 快速开始（Docker）

用 Docker Compose 是最简单的方式：

```bash
docker compose up -d
```

或者直接用 Docker 构建运行：

```bash
docker build -t fewreader .
docker run -d -p 8000:8000 -v $(pwd)/content:/app/content:ro --name fewreader fewreader
```

启动后在浏览器打开 **http://localhost:8000** 就可以了。

### 本地运行（Python）

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

### 添加内容

把 `.md` 或 `.txt` 文件丢进 `content/` 目录就行，子文件夹会自动变成侧边栏的分类：

```
content/
├── fiction/
│   └── my_story.txt
├── notes/
│   └── ideas.md
└── welcome.md
```

文件保存后立刻出现，不需要重启。

### 配置

能改的不多，但都在这里了：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CONTENT_DIR` | `content` | 文件存放路径，兼容旧版 `BOOKS_DIR`。 |
| `APP_TITLE` | `Fewreader` | 导航栏显示的标题。 |

### 技术栈

- **FastAPI** — 路由
- **Jinja2** — 模板渲染
- **python-markdown** — Markdown 解析
- **Tailwind CSS** — 样式

### 授权

[MIT](LICENSE)

---

## 繁體中文

一款輕量的自託管閱讀器，讓你在瀏覽器裡讀 `.md` 和 `.txt` 文件。沒有帳號、沒有雲端、沒有多餘的東西——只有你的內容，乾淨呈現。

**線上展示**：[read.fewlosophy.com](https://read.fewlosophy.com)

> 💡 **註**：本專案全程 100% vibe coding 打造。

### 快速開始（Docker）

用 Docker Compose 是最簡單的方式：

```bash
docker compose up -d
```

或者直接透過 Docker 建置並執行：

```bash
docker build -t fewreader .
docker run -d -p 8000:8000 -v $(pwd)/content:/app/content:ro --name fewreader fewreader
```

啟動後在瀏覽器開啟 **http://localhost:8000** 就可以了。

### 本地執行（Python）

```bash
# 安裝依賴套件
pip install -r requirements.txt

# 啟動開發伺服器
uvicorn app.main:app --reload --port 8000
```

### 新增內容

把 `.md` 或 `.txt` 檔案丟進 `content/` 目錄就好，子資料夾會自動成為側邊欄的分類：

```
content/
├── fiction/
│   └── my_story.txt
├── notes/
│   └── ideas.md
└── welcome.md
```

存檔後立即出現，不需要重啟服務。

### 設定

能調整的不多，都在這裡了：

| 變數 | 預設值 | 說明 |
|---|---|---|
| `CONTENT_DIR` | `content` | 檔案存放路徑，相容舊版 `BOOKS_DIR`。 |
| `APP_TITLE` | `Fewreader` | 導覽列顯示的標題。 |

### 技術棧

- **FastAPI** — 路由
- **Jinja2** — 模板渲染
- **python-markdown** — Markdown 解析
- **Tailwind CSS** — 樣式

### 授權條款

[MIT](LICENSE)
