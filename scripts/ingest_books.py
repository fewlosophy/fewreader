#!/usr/bin/env python3
"""Ingest public-domain books into the fewreader content/ tree.

Two source adapters (Project Gutenberg plain text, Wikisource chapters) feed
one output convention:

    content/<category>/<slug>/NN <chapter>.txt     # flowing, indented prose
    content/<category>/<slug>/<Book Title>.md      # intro/metadata + contents

Standard library only; no new dependencies on the reader app.

Examples:
    python scripts/ingest_books.py --ingest --book all          # fetch + write both
    python scripts/ingest_books.py --ingest --book republic --dry-run
    python scripts/ingest_books.py --resume --book guai          # backfill missing 回 only
    python scripts/ingest_books.py --reindex --book all          # offline: rebuild indexes
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
CONTENT = REPO / "content"
sys.path.insert(0, str(REPO / "scripts"))

import clean  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0 fewreader/1.0",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh,en;q=0.8",
}


def http_get(url: str, timeout: int = 60, retries: int = 6) -> bytes:
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 403, 500, 502, 503, 504):
                wait = min(60, 5 * (2 ** attempt))
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(5 * (2 ** attempt))
    raise RuntimeError(f"GET failed after {retries} retries: {last}")


def http_json(url: str, timeout: int = 60):
    return json.loads(http_get(url, timeout).decode("utf-8", "replace"))


def http_text(url: str, encoding: str = "utf-8", timeout: int = 90) -> str:
    return http_get(url, timeout).decode(encoding, "replace")


def slugify(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen] or "book"


def safe_filename(name: str) -> str:
    return re.sub(r'[\x00-\x1f"<>|?*\\/:]', "_", name).strip().strip(".")


# ---------------------------------------------------------------------------
# Project Gutenberg adapter
# ---------------------------------------------------------------------------
class RepublicAdapter:
    """Jowett's Republic (Gutenberg ebook 150); chapters = BOOK I..X."""

    title = "The Republic"
    category = "philosophy"
    slug = "republic"
    book_file = "The Republic"
    chapter_re = re.compile(r"^BOOK\s+[IVXLC]+$")
    source_url = "https://www.gutenberg.org/cache/epub/150/pg150.txt"


# ---------------------------------------------------------------------------
# Wikisource adapter
# ---------------------------------------------------------------------------
class GuiXianZhuangAdapter:
    """二十年目睹之怪現狀 (Weng Shao Mei, public domain) — 108 回 on zh.wikisource.

    Chapter pages are named `第001回`…`第108回` (3-digit padded). The
    prefixsearch index is occasionally stale and can miss some of them, so
    fetch_chapters() falls back to the canonical padded title for any gaps.
    """

    title = "二十年目睹之怪現狀"
    title_ascii = "Twenty Years in Which I Saw Strange Things"
    category = "fiction"
    slug = "ni-shi-nian-guai-xian-zhuang"
    book_file = "二十年目睹之怪現狀"
    book = "二十年目睹之怪現狀"
    chapter_total = 108
    chapter_re = re.compile(r"^第\d+回$")
    api = "https://zh.wikisource.org/w/api.php"
    base = "https://zh.wikisource.org"

    def _raw(self, title: str) -> str:
        q = urllib.parse.urlencode({"action": "raw", "title": title})
        return http_text(f"{self.base}/w/index.php?{q}", timeout=60)

    def _chapter_num(self, title: str) -> int:
        m = re.match(r"第(\d+)回", title.rsplit("/", 1)[-1])
        return int(m.group(1)) if m else 0

    def fetch_chapters(self) -> list[tuple[int, str, str]]:
        """All chapter 回, using prefixsearch where it has coverage and a
        per-chapter raw fallback for the gaps the stale index misses.

        `第N回` is canonical; the chapter total is fixed (chapter_total) so we
        always yield 1 … N, in order.
        """
        chapter_total = self.chapter_total

        # Cheap path: batch fetch for whatever the prefixsearch index knows about.
        indexed: dict[int, str] = {}
        try:
            titles = self._chapter_titles()
            by_num = {self._chapter_num(t): t for t in titles if re.match(r"^第\d+回$", t.rsplit("/", 1)[-1])}
            for start in range(0, len(by_num), 40):
                chunk = list(sorted(by_num))[start : start + 40]
                q = urllib.parse.urlencode({
                    "action": "query", "titles": "|".join(by_num[i] for i in chunk),
                    "prop": "revisions", "rvprop": "content", "rvslots": "main",
                    "format": "json", "formatversion": "2",
                })
                data = http_json(f"{self.api}?{q}", timeout=120)
                for page in data.get("query", {}).get("pages", []):
                    num = self._chapter_num(page.get("title", ""))
                    if num not in by_num:
                        continue
                    revs = page.get("revisions") or []
                    slots = (revs[0].get("slots") or {}).get("main", {}) if revs else {}
                    indexed[num] = slots.get("content", "")
            time.sleep(1.0)
        except Exception as e:  # fallback is required to make the book complete anyway
            print(f"    [warn] batch fetch failed: {type(e).__name__} {e}; falling back to per-chapter raw")

        out: list[tuple[int, str, str]] = []
        for n in range(1, chapter_total + 1):
            wt = indexed.get(n, "")
            if not wt:
                try:
                    wt = self._raw(f"{self.book}/第{n:03d}回")
                except Exception as e:
                    print(f"    [warn] 第{n:03d}回 not retrievable: {type(e).__name__}")
                    continue
            chap_title = self._chapter_title(wt)
            heading = f"第{n:03d}回 {chap_title}".strip()
            out.append((n, heading, self._strip_template(wt)))
        return out

    def _chapter_titles(self) -> list[str]:
        q = urllib.parse.urlencode({
            "action": "query", "list": "prefixsearch",
            "pssearch": self.book + "/第", "pslimit": "200",
            "format": "json", "formatversion": "2",
        })
        data = http_json(f"{self.api}?{q}", timeout=90)
        return [p["title"] for p in data.get("query", {}).get("prefixsearch", [])]

    @staticmethod
    def _chapter_title(raw: str) -> str:
        """Extract the chapter title from the {{Novel|...|title|...}} template.

        Strips the leading "第X回" that some sources duplicate (since we
        prefix our own numeric ordering). Accepts Arabic (第一回), Chinese
        (第一〇八回), or halfwidth digit (第二回) forms.
        """
        m = re.search(r"\{\{\s*Novel\s*\|\s*[^|\}]*\|\s*(.*?)\s*\|", raw, re.DOTALL)
        if not m:
            m = re.search(r"\{\{\s*Novel\s*\|\s*[^|\}]*\|\s*(.*?)\s*\}\}", raw, re.DOTALL)
        if not m:
            return ""
        t = m.group(1).replace("'''", "").replace("''", "").strip()
        t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
        t = re.sub(r"^\s*第\s*[\w\s\d\u4e00-\u9fff\u3000-\u303f]*?\s*回\s*", "", t)  # drop 第X回
        t = re.sub(r"[^\x20-\x7e\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2018\u2019\u201c\u201d/—–·()（）]", "", t)
        return re.sub(r"\s+", " ", t).strip()

    @staticmethod
    def _strip_template(raw: str) -> str:
        """Drop the {{Novel|...}} nav template / #REDIRECT lines; keep the body."""
        if "<onlyinclude>" in raw:
            raw = raw.split("<onlyinclude>", 1)[1]
            raw = raw.rsplit("</onlyinclude>", 1)[0]
        elif raw.lstrip().startswith("#REDIRECT"):
            return ""
        # remove any remaining {{...}} template block that sits on its own line
        raw = re.sub(r"^\s*\{\{.*?\}\}\s*\n?", "", raw, flags=re.DOTALL)
        # residual wikitext link syntax [[x|y]] -> label, [[x]] -> x
        raw = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", raw)
        return raw


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def write_chapter(root: Path, order: int, heading: str, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    name = safe_filename(heading) + ".txt" if _is_chinese_heading(heading) else safe_filename(f"{order:02d} {heading}") + ".txt"
    path = root / name
    path.write_text(body, encoding="utf-8")
    return path


def _is_chinese_heading(s: str) -> bool:
    """Chinese-headed chapters already carry an ordering token (第001回); don't
    re-prefix them with a zero-padded number — matches the hlm/ convention."""
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def write_index(root: Path, book: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    parts = [f"# {book['title']}", ""]
    if book.get("subtitle"):
        parts += [book["subtitle"], ""]
    if book.get("meta"):
        parts += book["meta"].splitlines()
        parts.append("")
    if book.get("intro"):
        parts += ["## Introduction", ""]
        parts += [l for l in book["intro"].rstrip().splitlines()]
        parts.append("")
    parts += ["## Contents", ""]
    for i, ch in enumerate(book["chapters"], 1):
        order, heading, body = ch
        fname_base = safe_filename(heading) if _is_chinese_heading(heading) else safe_filename(f"{order:02d} {heading}")
        fname = fname_base + ".txt"
        parts.append(f"{i:02d}. [{clean.normalize_typography(heading)}](./{urllib.parse.quote(fname, safe='')})")
    parts.append("")
    path = root / (book["book_file"] + ".md")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


META_KEYS = ("title", "author", "translator", "year", "source", "source_url", "description")


def write_meta(root: Path, book: dict) -> Path | None:
    """Write the .meta.json provenance record for a book.

    Reads `book['book_meta']` (a dict of known keys). If absent we derive a
    minimal one from the title/author/subtitle fields the ingest already knows.
    Returns the written path, or None if nothing to write (dry-run / empty).
    """
    meta = dict(book.get("book_meta") or {})
    if not meta and (book.get("author") or book.get("title")):
        # Fallback: build one from the legacy flat fields
        meta = {k: v for k, v in {"title": book.get("title"), "author": book.get("author")}.items() if v}
    if not meta:
        return None
    # Strip None / empty values to keep the JSON tidy
    clean = {k: meta[k] for k in META_KEYS if meta.get(k) not in (None, "")}
    if not clean:
        return None
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".meta.json"
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def summarize(name: str, files: list[Path]) -> None:
    total = sum(p.stat().st_size for p in files)
    print(f"  ✓ {name}: {len(files)} files, {total/1024:.0f} KiB")
    for p in files[:8]:
        print(f"      {p.name}")
    if len(files) > 8:
        print(f"      … +{len(files)-8} more")


def run_book(book: dict, dry_run: bool, skip: set[int] | None = None) -> None:
    """Write chapters (skipping any whose number is in `skip`), then rebuild the index from disk."""
    skip = skip or set()
    root = CONTENT / book["category"] / book["slug"]
    to_write = [c for c in book["chapters"] if c[0] not in skip]
    mode = "resuming" if skip else "writing"
    print(f"\n== {mode}: {book['title']}  ->  {root.relative_to(REPO)} "
          f"({len(to_write)} / {len(book['chapters'])} chapters) ==")
    for order, heading, body in to_write:
        if dry_run:
            print(f"    [dry-run] {order:03d} {clean.normalize_typography(heading)}  ({len(body)} chars)")
            continue
        write_chapter(root, order, heading, body)
        print(f"      wrote {order:03d}")
    if not dry_run:
        _rebuild_index_from_disk(root, book, intro=book.get("intro", ""))
        written_meta = write_meta(root, book)
        if written_meta:
            print(f"      wrote {written_meta.name}")
        summarize(root.name, sorted(root.glob("*.txt"), key=chapter_number))


def chapter_number(path: Path) -> int:
    """Chapter number encoded in a filename: 第001回… or 01 … (1-based)."""
    m = re.match(r"^第[0-9一二三四五六七八九十百千零〇○]+回", path.name)
    if m:
        digits = re.search(r"(\d+)", m.group(0))
        if digits:
            return int(digits.group(1))
    m = re.match(r"^(\d+)[ .]", path.name)
    return int(m.group(1)) if m else 0


def heading_for_path(path: Path) -> tuple[int, str]:
    """(order, heading) tuple that reproduces `path`'s name via write_chapter/write_index.

    Chinese chapters keep the full 第N回 prefix as their heading (matching how
    write_chapter named them); English ones drop the leading "NN " ordering token.
    """
    order = chapter_number(path)
    if _is_chinese_heading(path.name):
        return order, path.stem
    heading = re.sub(r"^\d+[ .]", "", path.stem)
    return order, heading


def disk_chapter_numbers(root: Path) -> set[int]:
    if not root.exists():
        return set()
    return {chapter_number(p) for p in root.glob("*.txt") if chapter_number(p)}


def _extract_intro_section(md_text: str) -> str:
    """Pull the body of the '## Introduction' section out of an index .md, if present."""
    m = re.search(r"^##\s+Introduction\s*$(.*?)(?=^##\s|\Z)", md_text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _rebuild_index_from_disk(root: Path, meta: dict, intro: str | None = None) -> Path:
    """Rebuild the book's index .md from the .txt chapters already on disk.

    `intro=None` preserves whatever Introduction the existing index already has,
    so an offline --reindex never silently drops it. An explicit value (even "")
    overrides it — used after an ingest so a new book gets its fetched intro.
    """
    if not root.exists() or not list(root.glob("*.txt")):
        raise SystemExit(f"No .txt chapters found under {root}")
    if intro is None:
        index = next((p for p in root.glob("*.md")), None)
        intro = _extract_intro_section(index.read_text(encoding="utf-8")) if index else ""
    book = dict(meta)
    book["intro"] = intro
    book["chapters"] = [heading_for_path(p) + ("",) for p in sorted(root.glob("*.txt"), key=chapter_number)]
    return write_index(root, book)


BOOKS = {
    "republic": {
        "title": "The Republic",
        "category": RepublicAdapter.category,
        "slug": RepublicAdapter.slug,
        "book_file": RepublicAdapter.book_file,
        "subtitle": "by Plato · translated by Benjamin Jowett (1871)",
        "meta": "Project Gutenberg eBook #150",
        "book_meta": {
            "title": "The Republic",
            "author": "Plato",
            "translator": "B. Jowett",
            "year": 380,
            "source": "Project Gutenberg #150",
            "source_url": "https://www.gutenberg.org/cache/epub/150/pg150.txt",
            "description": "Plato's dialogue on justice and the ideal state, in Benjamin Jowett's 1871 translation.",
        },
    },
    "guai": {
        "title": "二十年目睹之怪現狀",
        "category": GuiXianZhuangAdapter.category,
        "slug": GuiXianZhuangAdapter.slug,
        "book_file": GuiXianZhuangAdapter.book_file,
        "subtitle": "滄海亭主人 (Weng Shao Mei, pseud.)",
        "meta": "zh.wikisource.org — public domain",
        "book_meta": {
            "title": "二十年目睹之怪現狀",
            "author": "滄海亭主人 (Weng Shao Mei)",
            "year": 1905,
            "source": "Chinese Wikisource",
            "source_url": "https://zh.wikisource.org/wiki/二十年目睹之怪現狀",
            "description": "Late-Qing social satirical novel of the 'four great novels of the late Qing'.",
        },
    },
}


FETCHERS = {
    "republic": lambda: _ingest_republic(),
    "guai": lambda: _ingest_guai_xian(),
}


def _book_meta(key: str) -> dict:
    meta = BOOKS.get(key)
    if not meta:
        raise SystemExit(f"Unknown book '{key}' (expected one of {', '.join(BOOKS)})")
    return meta


def reindex_book(key: str) -> Path:
    """Offline: rebuild the index .md + .meta.json from chapters already on disk. No network."""
    meta = _book_meta(key)
    root = CONTENT / meta["category"] / meta["slug"]
    n = len([p for p in root.glob("*.txt")])
    idx = _rebuild_index_from_disk(root, meta)  # intro preserved from existing index
    wmeta = write_meta(root, meta)
    detail = f" -> {wmeta.name}" if wmeta else ""
    print(f"  ✓ {root.relative_to(REPO)}: reindexed {n} chapters -> {idx.name}{detail}")
    return idx


def resume_book(key: str, dry_run: bool) -> None:
    """Re-fetch the book and write only the chapters still missing on disk, then reindex.

    Idempotent: chapters already present are skipped. Backfills a partially-written
    ingest; it cannot conjure chapters the source itself lacks.
    """
    meta = _book_meta(key)
    book = {**meta, **FETCHERS[key]()}
    skip = disk_chapter_numbers(CONTENT / meta["category"] / meta["slug"])
    have = {o for o, _, _ in book["chapters"]}
    will_write = sorted(have - skip)
    print(f"    on disk: {len(skip)}  |  this fetch: {len(have)}  |  to write: {len(will_write)}")
    if will_write:
        print(f"    chapters to (re)write: {will_write}")
    elif have <= skip:
        print("    already complete — only the index is rebuilt")
    run_book(book, dry_run=dry_run, skip=skip)


def _ingest_republic() -> dict:
    print("== Fetching: The Republic (Gutenberg 150) ==")
    text = http_text(RepublicAdapter.source_url)
    body = clean.strip_pg_boilerplate(text)
    preamble, chs = clean.clean_to_chapters(body, RepublicAdapter.chapter_re)
    chs = [(i, h, b) for i, (h, b) in enumerate(chs, 1)]
    print(f"    {len(chs)} chapters (first: {chs[0][1]})")

    dialogue_intro = ""
    m = re.search(r"^THE\s+INTRODUCTION\b[\s\S]*$", preamble, re.MULTILINE)
    if m:
        intro_span = m.group(0)
        cut = re.search(r"^BOOK\s+[IVXLC]+", intro_span, re.MULTILINE)
        if cut:
            intro_span = intro_span[: cut.start()]
        dialogue_intro = clean.clean_paragraphs(intro_span)

    return {
        "title": RepublicAdapter.title,
        "subtitle": "by Plato · translated by Benjamin Jowett (1871)",
        "meta": "Project Gutenberg eBook #150",
        "category": RepublicAdapter.category,
        "slug": RepublicAdapter.slug,
        "book_file": RepublicAdapter.book_file,
        "intro": dialogue_intro,
        "chapters": chs,
    }


def _ingest_guai_xian() -> dict:
    print("== Fetching: 二十年目睹之怪現狀 (zh.wikisource) ==")
    adapter = GuiXianZhuangAdapter()
    raw = adapter.fetch_chapters()
    print(f"    {len(raw)} 回 ({raw[0][1]} … {raw[-1][1]})")
    return {
        "title": "二十年目睹之怪現狀",
        "subtitle": "滄海亭主人 (Weng Shao Mei, pseud.)",
        "meta": "zh.wikisource.org — public domain",
        "category": adapter.category,
        "slug": adapter.slug,
        "book_file": adapter.book_file,
        "intro": "",
        "chapters": [(n, l, clean.clean_paragraphs(b)) for n, l, b in raw],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ingest", action="store_true", help="fetch from source and write all chapters (default)")
    grp.add_argument("--resume", action="store_true", help="re-fetch, but only write chapters missing on disk, then reindex")
    grp.add_argument("--reindex", action="store_true", help="offline: rebuild the index .md from chapters on disk (no network)")
    ap.add_argument("--book", choices=["all", "republic", "guai"], default="all", help="which book to act on")
    ap.add_argument("--dry-run", action="store_true", help="print plan without writing")
    args = ap.parse_args()

    keys = ("republic", "guai") if args.book == "all" else (args.book,)
    for key in keys:
        if args.reindex:
            reindex_book(key)
        elif args.resume:
            resume_book(key, args.dry_run)
        elif args.ingest:
            meta = _book_meta(key)
            run_book({**meta, **FETCHERS[key]()}, args.dry_run)
    print("\nDone.")


if __name__ == "__main__":
    main()
