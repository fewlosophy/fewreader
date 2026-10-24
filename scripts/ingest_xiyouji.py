#!/usr/bin/env python3
"""Ingest 西遊記 (100 回) from zh.wikisource into content/fiction/xiyouji.

The book uses the {{header|...|section=第一回<br>回目}} template, so the
chapter title has to come from the `section` parameter (the {{Novel|...}}
parser used by ingest_books.py does not see it). Wikisource verse lines use
leading ':' definition-list markers and must keep their own line breaks.

Usage:
    python3 scripts/ingest_xiyouji.py --limit 3     # smoke test
    python3 scripts/ingest_xiyouji.py               # all 100 回
    python3 scripts/ingest_xiyouji.py --resume      # skip chapters on disk
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import clean  # noqa: E402

BOOK = "西遊記"
TOTAL = 100
CATEGORY = "fiction"
SLUG = "xiyouji"
OUT = REPO / "content" / CATEGORY / SLUG
API = "https://zh.wikisource.org/w/index.php"
UA = {"User-Agent": "fewreader-ingest/1.0 (personal reader; contact: local)"}

META = {
    "title": BOOK,
    "author": "吳承恩",
    "year": 1592,
    "source": "Chinese Wikisource",
    "source_url": "https://zh.wikisource.org/wiki/西遊記",
    "license": "PD-old-50 / page text CC BY-SA",
    "pd_basis": "作者吳承恩（約1500–1582）逝世逾50年，作品屬公有領域；章節文字取自中文維基文庫，該站頁面內容以 CC BY-SA 授權，轉載須標註來源。",
    "description": "明代吳承恩所著章回小說，一百回，中國四大名著之一。",
}

HEADER_RE = re.compile(r"\{\{\s*header\b(.*?)\}\}", re.S | re.I)
SECTION_RE = re.compile(r"\|\s*section\s*=\s*(.*?)(?=\n\s*\||\Z)", re.S)
TEMPLATE_RE = re.compile(r"\{\{.*?\}\}", re.S)
VARIANT_RE = re.compile(r"\{\{\s*另\s*\|\s*([^|}]*)[^}]*\}\}")  # {{另|主|王}} -> 主
LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
CN_PREFIX_RE = re.compile(r"^\s*第\s*[一二三四五六七八九十百零〇○\d]+\s*回\s*")


def http_text(url: str, retries: int = 5, timeout: int = 60) -> str:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(min(30, 2 * (attempt + 1) ** 2))
    raise RuntimeError(f"GET failed: {url} ({last})")


def header_block(raw: str) -> str:
    """Extract the {{header ...}} block by brace matching.

    A regex stops at the first '}}' — which is inside nested templates such as
    {{另|主|王}} — and silently truncates the section value.
    """
    i = raw.find("{{header")
    if i < 0:
        return ""
    depth, j = 0, i
    while j < len(raw) - 1:
        two = raw[j:j + 2]
        if two == "{{":
            depth += 1
            j += 2
            continue
        if two == "}}":
            depth -= 1
            j += 2
            if depth == 0:
                return raw[i:j]
            continue
        j += 1
    return ""


def chapter_title(raw: str) -> str:
    """回目 from the {{header|...|section=第一回<br>回目}} template."""
    hb = header_block(raw)
    if not hb:
        return ""
    inner = hb[len("{{header"):]
    inner = inner[: inner.rfind("}}")]
    s = SECTION_RE.search(inner)
    if not s:
        return ""
    t = VARIANT_RE.sub(r"\1", s.group(1))
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = TEMPLATE_RE.sub("", t)
    t = LINK_RE.sub(r"\1", t)
    t = re.sub(r"《本作[^》]*》", "", t)
    t = t.replace("'''", "").replace("''", "")
    t = CN_PREFIX_RE.sub("", t.strip())
    t = re.sub(r"[{}|]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clean_body(raw: str) -> str:
    """Strip templates, then format paragraphs; ':' verse runs keep line breaks."""
    hb = header_block(raw)
    body = raw.replace(hb, "", 1) if hb else raw
    body = VARIANT_RE.sub(r"\1", body)
    body = re.sub(r"__\w+__", "", body)
    body = TEMPLATE_RE.sub("", body)
    body = LINK_RE.sub(r"\1", body)
    body = body.replace("'''", "").replace("''", "")
    body = re.sub(r"(?m)^\s*<[^>]+>\s*$", "", body)

    paras: list[str] = []
    for block in re.split(r"\n\s*\n+", body):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if any(ln.lstrip().startswith(":") for ln in lines):
            # Wikisource verse: a run of ':' lines, often preceded by a label
            # such as 詩曰： which must stay on its own line.
            verse = [clean.normalize_typography(re.sub(r"^\s*:+\s*", "", ln)).strip() for ln in lines]
            verse = [v for v in verse if v]
            if verse:
                paras.append("    " + "\n    ".join(verse))
            continue
        joined = " ".join(ln.strip() for ln in lines)
        joined = re.sub(r"\s+", " ", clean.normalize_typography(joined)).strip()
        if joined:
            paras.append("    " + joined)
    return "\n\n".join(paras) + "\n" if paras else ""


def safe_name(s: str) -> str:
    s = re.sub(r'[\x00-\x1f"<>|?*\\/:]', " ", s)
    return re.sub(r"\s+", " ", s).strip().rstrip(".")


def chapter_files() -> dict[int, Path]:
    if not OUT.exists():
        return {}
    out: dict[int, Path] = {}
    for p in OUT.glob("*.txt"):
        m = re.match(r"^第(\d{3})回", p.name)
        if m:
            out[int(m.group(1))] = p
    return out


def write_index() -> Path:
    lines = [f"# {META['title']}", "", f"{META['author']} · 一百回", "",
             f"來源：{META['source']} — {META['source_url']}", "",
             f"授權：{META['license']}", "", META["pd_basis"], "", "## 目錄", ""]
    for n, p in sorted(chapter_files().items()):
        title = p.stem[len(f"第{n:03d}回"):].strip()
        lines.append(f"{n:03d}. [{title}](./{urllib.parse.quote(p.name, safe='')})")
    lines.append("")
    path = OUT / f"{BOOK}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after N chapters")
    ap.add_argument("--resume", action="store_true", help="skip chapters already on disk")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    have = chapter_files() if args.resume else {}
    wrote = skipped = failed = 0
    todo = range(1, TOTAL + 1)
    for n in todo:
        if n in have:
            skipped += 1
            continue
        if args.limit and wrote >= args.limit:
            break
        title_zh = f"第{n:03d}回"
        url = f"{API}?" + urllib.parse.urlencode({"action": "raw", "title": f"{BOOK}/{title_zh}"})
        try:
            raw = http_text(url)
        except Exception as e:  # noqa: BLE001
            print(f"  [fail] {title_zh} fetch: {e}")
            failed += 1
            continue
        title = chapter_title(raw)
        body = clean_body(raw)
        if not title or len(body) < 500:
            print(f"  [fail] {title_zh}: title={title!r} chars={len(body)}")
            failed += 1
            continue
        path = OUT / f"{safe_name(title_zh + ' ' + title)}.txt"
        path.write_text(body, encoding="utf-8")
        wrote += 1
        print(f"  ok {path.name} ({len(body)} chars)")
        time.sleep(0.4)

    idx = write_index()
    (OUT / ".meta.json").write_text(json.dumps(META, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = len(chapter_files())
    print(f"\n[done] wrote={wrote} skipped={skipped} failed={failed} on_disk={total}/{TOTAL}")
    print(f"[done] {idx.relative_to(REPO)}")
    return 0 if total == TOTAL else 1


if __name__ == "__main__":
    sys.exit(main())
