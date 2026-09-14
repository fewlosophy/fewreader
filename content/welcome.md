# Welcome to Fewreader

Fewreader is a clean, distraction-free reading app for your Markdown and plain-text files.
No clutter — just you and your words.

## Features

- 📖 Render `.md` and `.txt` files beautifully
- 🌙 Dark and light theme toggle
- 📂 Sub-folder aware library browser
- 📑 Automatic table of contents from headings
- 🔗 Fast navigation between documents

## Getting Started

Browse the library on the left to find your books and notes, or drop new `.md` and `.txt`
files into the `content/` directory and they'll appear automatically.

## Markdown Support

Fewreader supports standard CommonMark including:

### Inline formatting

You can use **bold**, *italic*, `inline code`, and [links](https://example.com).

### Code blocks

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

print(greet("reader"))
```

### Tables

| Format | Extension | Renders |
|--------|-----------|---------|
| Markdown | `.md` | Full CommonMark |
| Plain text | `.txt` | Paragraph-wrapped |

### Lists

1. Open the library
2. Pick an item
3. Start reading

- Keyboard-friendly navigation
- Responsive layout
- Zero runtime dependencies on the frontend

## Tip

You can organise files into sub-folders inside `content/` for categories:

```
content/
├── fiction/
│   └── my_novel.txt
├── notes/
│   └── project_ideas.md
└── welcome.md
```

Happy reading!
