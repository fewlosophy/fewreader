from pathlib import Path

import markdown as md_lib


def convert(file_path: Path) -> tuple[str, str]:
    """
    Convert a .md or .txt file to HTML.

    Returns:
        (html_content, toc_html)  — toc_html is empty string for .txt files.
    """
    ext = file_path.suffix.lower()

    if ext == ".md":
        return _convert_markdown(file_path)
    elif ext == ".txt":
        return _convert_plaintext(file_path), ""
    else:
        raise ValueError(f"Unsupported extension: {ext}")


def _convert_markdown(file_path: Path) -> tuple[str, str]:
    text = file_path.read_text(encoding="utf-8")
    converter = md_lib.Markdown(
        extensions=["toc", "fenced_code", "tables"],
        extension_configs={
            "toc": {
                "title": "Contents",
                "toc_depth": "2-4",
            }
        },
    )
    html = converter.convert(text)
    toc = converter.toc  # type: ignore[attr-defined]  # added by toc extension
    return html, toc


def _convert_plaintext(file_path: Path) -> str:
    text = file_path.read_text(encoding="utf-8")
    # Split on blank lines → paragraphs; single newlines → <br>
    paragraphs = text.split("\n\n")
    parts = []
    for para in paragraphs:
        stripped = para.strip()
        if stripped:
            inner = stripped.replace("\n", "<br>\n")
            parts.append(f"<p>{inner}</p>")
    return "\n".join(parts)
