#!/usr/bin/env python3
"""
Batch reformatter for Crime and Punishment chapter text files.

Transforms legacy Project Gutenberg text formatting into modern digital reading typography:
1. Unwraps hard-wrapped lines (70-character wraps) within paragraphs so text flows smoothly
   across responsive screen viewports without artificial <br> line breaks.
2. Converts ASCII typewriter double-hyphens ('--') to typographical em-dashes ('—').
3. Normalizes excessive ellipsis dots ('....' / '...') to standard typographical ellipsis ('…').
4. Cleans legacy ASCII underscores ('_word_') used for italics into clean prose.
5. Collapses redundant consecutive whitespace within lines.
6. Preserves clear paragraph separations and chapter/part headers.
"""

from pathlib import Path
import re
import sys


def is_header(s: str) -> bool:
    clean = s.strip()
    if clean.startswith("TRANSLATOR") and "PREFACE" in clean:
        return True
    if re.match(r"^PART\s+[IVXLCDM]+$", clean, re.IGNORECASE):
        return True
    if re.match(r"^CHAPTER\s+[IVXLCDM]+$", clean, re.IGNORECASE):
        return True
    if clean.upper() == "EPILOGUE":
        return True
    if clean in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII"):
        return True
    return False


def format_chapter_text(raw_text: str) -> str:
    # 1. Replace typewriter hyphens with em-dash
    text = raw_text.replace("---", "—").replace("--", "—")

    # 2. Normalize ellipses (3 or more dots) to unicode ellipsis character
    text = re.sub(r"\.{3,}", "…", text)

    # 3. Strip legacy ASCII italics markup underscores (_word_ -> word)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # 4. Split into paragraph blocks on double or multiple newlines
    blocks = re.split(r"\n\s*\n+", text)
    formatted_blocks = []

    for block in blocks:
        # Strip each line and normalize internal spaces
        lines = [re.sub(r"[^\S\r\n]{2,}", " ", line.strip()) for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        # Join lines within the paragraph into a continuous flowing line
        paragraph = " ".join(lines)
        if is_header(paragraph):
            formatted_blocks.append(paragraph)
        else:
            formatted_blocks.append("    " + paragraph)

    return "\n\n".join(formatted_blocks) + "\n"


def batch_reformat(target_dir: Path) -> None:
    txt_files = sorted(target_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {target_dir}", file=sys.stderr)
        return

    print(f"Reformatting {len(txt_files)} chapter files in {target_dir}...")
    for file_path in txt_files:
        original = file_path.read_text(encoding="utf-8")
        formatted = format_chapter_text(original)
        file_path.write_text(formatted, encoding="utf-8")
        print(f"  ✓ {file_path.name}: {len(original.splitlines())} lines → {len(formatted.splitlines())} lines")

    print("Batch reformatting complete!")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1]).resolve()
    else:
        target_dir = base_dir / "books" / "fiction" / "crime-and-punishment"
    batch_reformat(target_dir)
