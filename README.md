# ReadLite

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](Dockerfile)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](#)

[English](#readlite) | [繁體中文](#繁體中文)

A clean, self-hosted web app for reading `.md` and `.txt` files in your browser.

## Quick Start (Docker)

Run with Docker Compose:

```bash
docker compose up -d
```

Or build and run with Docker directly:

```bash
docker build -t readlite .
docker run -d -p 8000:8000 -v $(pwd)/content:/app/content:ro --name readlite readlite
```

Then open **http://localhost:8000** in your browser.

## Local Setup (Python)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload --port 8000
```

## Adding Books & Notes

Drop `.md` or `.txt` files into the `content/` directory. Sub-folders become categories:

```
content/
├── fiction/
│   └── my_story.txt
├── notes/
│   └── ideas.md
└── welcome.md
```

Changes are picked up automatically — no restart needed.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `CONTENT_DIR` | `content` | Path to content directory (legacy `BOOKS_DIR` also supported) |
| `APP_TITLE` | `ReadLite` | Site title shown in the nav |

## Stack

- **FastAPI** — routing
- **Jinja2** — server-side rendering
- **python-markdown** — CommonMark conversion
- **Tailwind CSS** — styling

## License

[MIT](LICENSE)

---

## 繁體中文

簡潔、清爽的自託管 Web 閱讀器，支援在瀏覽器中閱讀 `.md` 與 `.txt` 格式的書籍與筆記。

### 快速開始 (Docker)

使用 Docker Compose 啟動：

```bash
docker compose up -d
```

或直接透過 Docker 建置並執行：

```bash
docker build -t readlite .
docker run -d -p 8000:8000 -v $(pwd)/content:/app/content:ro --name readlite readlite
```

啟動後請在瀏覽器中開啟 **http://localhost:8000**。

### 本地環境設定 (Python)

```bash
# 安裝依賴套件
pip install -r requirements.txt

# 啟動開發伺服器
uvicorn app.main:app --reload --port 8000
```

### 新增書籍與筆記

將 `.md` 或 `.txt` 檔案放入 `content/` 目錄中。支援子資料夾層級，子資料夾會自動作為分類目錄顯示：

```
content/
├── fiction/
│   └── my_story.txt
├── notes/
│   └── ideas.md
└── welcome.md
```

檔案變更會自動即時更新，無需重新啟動服務。

### 設定選項

| 環境變數 | 預設值 | 說明 |
|---|---|---|
| `CONTENT_DIR` | `content` | 內容檔案存放路徑（亦相容 `BOOKS_DIR`） |
| `APP_TITLE` | `ReadLite` | 網站與導覽列顯示的標題 |

### 技術棧

- **FastAPI** — 路由與後端服務
- **Jinja2** — 伺服器端 HTML 模板渲染
- **python-markdown** — Markdown 解析與目錄 (TOC) 生成
- **Tailwind CSS** — 樣式呈現與響應式設計

### 授權條款

[MIT](LICENSE)


