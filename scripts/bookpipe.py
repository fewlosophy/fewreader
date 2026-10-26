#!/usr/bin/env python3
"""Registry-driven public-domain book ingestion for fewreader.

Adding a book = one [[book]] block in scripts/books.toml, then:

    python3 scripts/bookpipe.py --book <slug>          # fetch + clean + validate + promote
    python3 scripts/bookpipe.py --all                  # every book in the registry
    python3 scripts/bookpipe.py --book <slug> --dry-run # plan only, no writes
    python3 scripts/bookpipe.py --book <slug> --reindex # offline: rebuild index from disk
    python3 scripts/bookpipe.py --book <slug> --validate-only

Guarantee: a book either lands complete in content/<category>/<slug>/ or not at
all. Everything is written to content/.staging/<slug>/ first, all validators must
pass, and only then is the directory promoted. On failure the staging tree stays
for inspection, a REPORT.md lists every failed check, and the exit code is 1.

Stdlib only (tomllib, urllib, sqlite-free). Reuses scripts/clean.py.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import time
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"
STAGING = CONTENT / ".staging"
REGISTRY = Path(__file__).resolve().parent / "books.toml"
sys.path.insert(0, str(REPO / "scripts"))
import clean  # noqa: E402

UA = {"User-Agent": "fewreader-bookpipe/1.0 (personal reader; contact: local)"}
WIKISOURCE_API = "https://zh.wikisource.org/w/index.php"
INDENT = "\u3000\u3000"  # 兩個漢字寬，對照 content/fiction/hlm
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
VARIANT_RE = re.compile(r"\{\{\s*另\s*\|\s*([^|}]*)[^}]*\}\}")   # {{另|主|王}} -> 主
VARIANT2_RE = re.compile(r"\{\{\s*另2\s*\|\s*([^|}]*)[^}]*\}\}")  # {{另2|用胡服|四庫版作…}} -> 用胡服
PIANZI_RE = re.compile(r"\{\{\s*僻字\s*\|\s*([^|}]*)[^}]*\}\}")   # {{僻字|𩎃|左革右燮}} -> 𩎃
TEMPLATE_RE = re.compile(r"\{\{.*?\}\}", re.S)
LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
SECTION_RE = re.compile(r"\|\s*section\s*=\s*(.*?)(?=\n\s*\||\Z)", re.S)
NOVEL_RE = re.compile(r"\{\{\s*Novel\s*\|[^|}]*\|\s*(.*?)\s*[|}]", re.S)
CN_PREFIX_RE = re.compile(r"^\s*第\s*[一二三四五六七八九十百零〇○\d]+\s*[回章節节卷集]\s*")
CN_VOLUME_RE = re.compile(r"^\s*卷\s*[一二三四五六七八九十百零〇○\d]+\s*")
# ==卷一== / ===故事=== (補筆談) and <center>=故事一=</center> (正卷) are both
# section titles; render them as 【…】 so the reader keeps the structure.
CENTER_HEAD_RE = re.compile(r"<center>\s*={1,6}\s*(.+?)\s*={1,6}\s*</center>", re.I | re.S)
WIKI_HEAD_RE = re.compile(r"(?m)^[ \t]*(={1,6})[ \t]*([^=\n]+?)[ \t]*\1[ \t]*$")
STRAY_EQ_RE = re.compile(r"(?m)^[ \t]*={1,6}[ \t]*$")
REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.I | re.S)
YL_RE = re.compile(r"\{\{\s*YL\s*\|\s*([^|}]*)[^}]*\}\}")   # {{YL|癸丑|1613年}} -> 癸丑
# {{專|黃帝}} / {{書|札記}} / {{標|幼而徇齊}} annotate a name or a reading; the
# display text is the first positional arg, so dropping the template would delete
# the word itself. Everything else ({{注意}}, {{wikipedia}}, {{Textquality}},
# {{樣式:舊體詩}}, …) is page furniture and is dropped.
DISPLAY_TEMPLATES = {"專", "書", "標", "另", "另2", "僻字", "YL", "註", "人名"}
INNER_TEMPLATE_RE = re.compile(r"\{\{([^{}]*)\}\}")
POEM_RE = re.compile(r"<poem[^>]*>(.*?)</poem>", re.I | re.S)
# Language-variant markup: -{zh:鍾;zh-hans:钟;zh-hant:鍾;}- -> 鍾
VARIANT_MARK_RE = re.compile(r"-\{(.*?)\}-", re.S)
HEADING_OUT_RE = re.compile(r"^【.*】$")
ANY_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
INCLUDE_TAG_RE = re.compile(r"</?(?:onlyinclude|noinclude|includeonly)\s*>", re.I)
RESIDUAL_RE = re.compile(r"\{\{|\}\}|\[\[|\]\]|__\w+__|<br\s*/?>|&lt;", re.I)
# [[Category:X]] / [[File:X]] / [[:Category:X]] are page furniture, not prose.
META_LINK_RE = re.compile(r"\[\[\s*:?\s*(?:Category|File|Image)\s*:[^\]]*\]\]", re.I)
META_CAT_RE = re.compile(r"\[\[\s*Category\s*:[^\]]*\]\]", re.I)


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
def load_registry(path: Path = REGISTRY) -> dict[str, dict]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    books = {}
    for b in data.get("book", []):
        for key in ("slug", "title", "category", "source"):
            if not b.get(key):
                raise SystemExit(f"books.toml: entry missing '{key}': {b}")
        books[b["slug"]] = b
    return books


# --------------------------------------------------------------------------- #
# http
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# wikitext helpers
# --------------------------------------------------------------------------- #
def header_block(raw: str) -> str:
    """{{header ...}} by brace matching; a regex stops inside {{另|a|b}}.

    Case-insensitive: some pages use {{Header ...}} (e.g. 徐霞客遊記/滇遊日記一,
    whose section carries a nested {{color|red|闕}}). Matching only lowercase
    left the whole header in the body, and the non-greedy TEMPLATE_RE then cut it
    at the inner braces, leaving an orphan '}}'.
    """
    m = re.search(r"\{\{\s*header", raw, re.I)
    if not m:
        return ""
    i = m.start()
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


def _clean_title(t: str) -> str:
    t = VARIANT_RE.sub(r"\1", t)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = TEMPLATE_RE.sub("", t)
    t = LINK_RE.sub(r"\1", t)
    t = re.sub(r"《本作[^》]*》", "", t)
    t = t.replace("'''", "").replace("''", "")
    t = CN_PREFIX_RE.sub("", t.strip())
    t = re.sub(r"[{}|]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def wikisource_title(raw: str, profile: str) -> str:
    if profile == "wikisource-header":
        hb = header_block(raw)
        if not hb:
            return ""
        inner = hb[len("{{header"):]
        inner = inner[: inner.rfind("}}")]
        m = SECTION_RE.search(inner)
        return _clean_title(m.group(1)) if m else ""
    if profile == "wikisource-novel":
        m = NOVEL_RE.search(raw)
        return _clean_title(m.group(1)) if m else ""
    raise SystemExit(f"unknown wikisource profile '{profile}'")


def _split_args(inner: str) -> list[str]:
    """Split template args on '|' but not inside [[a|b]] (the pipe is a link label)."""
    parts, buf, depth = [], [], 0
    i = 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two == "[[":
            depth += 1
            buf.append(two)
            i += 2
            continue
        if two == "]]" and depth:
            depth -= 1
            buf.append(two)
            i += 2
            continue
        ch = inner[i]
        if ch == "|" and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _expand_templates(body: str) -> str:
    """Expand innermost templates, keeping display text for annotation templates.

    Runs bottom-up so nested markup ({{標|{{專|幼而徇齊}}}}) resolves; 12 passes is
    ample for Wikisource nesting depth.
    """
    def one(m: re.Match) -> str:
        parts = _split_args(m.group(1))
        name = parts[0].strip()
        if name in DISPLAY_TEMPLATES:
            for arg in parts[1:]:
                if "=" not in arg and arg.strip():
                    return arg.strip()
            return ""
        # Wrapper templates ({{center block|<poem>…}}, {{center|…}}) hold real
        # body text; meta boxes ({{wikipedia|X}}, {{Textquality|100%}},
        # {{注意|text=…}}) are short or use named args. Keep the former.
        if len(parts) > 1 and "=" not in parts[1] and len(parts[1].strip()) > 30:
            return parts[1]
        return ""

    for _ in range(12):
        new = INNER_TEMPLATE_RE.sub(one, body)
        if new == body:
            break
        body = new
    return body


def _variant_marks(body: str) -> str:
    """Resolve -{zh:鍾;zh-hans:钟;zh-hant:鍾;}- to the traditional form."""
    def one(m: re.Match) -> str:
        inner = m.group(1)
        if ";" not in inner:
            return inner
        pairs = {}
        for part in inner.split(";"):
            if ":" in part:
                k, _, v = part.partition(":")
                pairs[k.strip().lstrip("-")] = v.strip()
        for key in ("zh-hant", "zh-tw", "zh", "zh-hans"):
            if pairs.get(key):
                return pairs[key]
        return inner
    return VARIANT_MARK_RE.sub(one, body)


def _flatten_tables(body: str) -> str:
    """Turn wikitext tables into one cell per line (as verse, so breaks survive).

    The 史記 年表 volumes are literally tables; without this the reader gets a wall
    of '|' cell separators. Cell attribute prefixes (align=… |) are stripped.
    """
    out: list[str] = []
    in_table = False
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith("{|"):
            in_table = True
            continue
        if s.startswith("|}"):
            in_table = False
            out.append("")
            continue
        if not in_table:
            out.append(ln)
            continue
        if s.startswith("|-") or not s:
            continue
        if s.startswith(("|", "!")):
            cell = s.lstrip("|!").strip()
            if "|" in cell:
                head, _, rest = cell.partition("|")
                cell = rest.strip() if "=" in head else cell.replace("|", "　")
            if cell:
                out.append(":" + cell)
            continue
        out.append(":" + s)
    return "\n".join(out)


def wikitext_body(raw: str) -> str:
    """Strip the header/templates, format paragraphs; ':' verse runs keep breaks."""
    hb = header_block(raw)
    body = raw.replace(hb, "", 1) if hb else raw
    body = INCLUDE_TAG_RE.sub("", body)
    body = REF_RE.sub("", body)
    body = META_LINK_RE.sub("", body)
    body = _variant_marks(body)
    body = _expand_templates(body)
    body = TEMPLATE_RE.sub("", body)
    # Stray braces survive on pages whose source is unbalanced (史記/卷027 has an
    # orphan '}}' mid-text). Expansion has already run, so any leftover here is
    # source damage, not an unhandled template — drop it.
    body = body.replace("{{", "").replace("}}", "")
    body = re.sub(r"__\w+__", "", body)
    body = LINK_RE.sub(r"\1", body)
    body = body.replace("'''", "").replace("''", "")
    # <poem> keeps one line per verse line; prefix ':' so the block loop below
    # treats it as verse instead of joining it into a single run-on line.
    body = POEM_RE.sub(
        lambda m: "\n\n" + "\n".join(
            ":" + ln for ln in m.group(1).strip().splitlines() if ln.strip()
        ) + "\n\n",
        body,
    )
    # Section titles: <center>=故事一=</center> and ==卷一== -> 【…】
    body = CENTER_HEAD_RE.sub(lambda m: f"\n\n【{m.group(1).strip()}】\n\n", body)
    body = WIKI_HEAD_RE.sub(lambda m: f"\n\n【{m.group(2).strip()}】\n\n", body)
    body = STRAY_EQ_RE.sub("", body)
    body = ANY_TAG_RE.sub("", body)
    body = _flatten_tables(body)
    body = html.unescape(body)
    # U+FFFD means the source page itself carries a corrupted character
    # (日知錄/卷20 has 《書·金<U+FFFD>》 for 金縢). Drop it and say so, rather than
    # failing the whole volume over one byte.
    if "\ufffd" in body:
        n_bad = body.count("\ufffd")
        print(f"   ! dropped {n_bad} U+FFFD from source text")
        body = body.replace("\ufffd", "")
    body = re.sub(r"(?m)^\s*<[^>]+>\s*$", "", body)

    paras: list[str] = []
    for block in re.split(r"\n\s*\n+", body):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if len(lines) == 1 and HEADING_OUT_RE.match(lines[0].strip()):
            paras.append(lines[0].strip())
            continue
        if any(ln.lstrip().startswith(":") for ln in lines):
            verse = [clean.normalize_typography(re.sub(r"^\s*:+\s*", "", ln)).strip() for ln in lines]
            verse = [v for v in verse if v]
            if verse:
                paras.append(INDENT + ("\n" + INDENT).join(verse))
            continue
        joined = re.sub(r"\s+", " ", clean.normalize_typography(" ".join(ln.strip() for ln in lines))).strip()
        if joined:
            paras.append(INDENT + joined)
    return "\n\n".join(paras) + "\n" if paras else ""


def _body_heading(body: str) -> str:
    """First 【…】 section title in the body, if any.

    卷十七/二十/二十二/二十三/二十四/二十六 name no topic in their header, but
    the body opens with 【書畫】/【神奇】/… — use that so the filename is not just
    a bare volume number.
    """
    for line in body.splitlines():
        s = line.strip()
        if HEADING_OUT_RE.match(s):
            return s[1:-1].strip()
    return ""


def safe_name(s: str) -> str:
    s = re.sub(r'[\x00-\x1f"<>|?*\\/:]', " ", s)
    return re.sub(r"\s+", " ", s).strip().rstrip(".")


# --------------------------------------------------------------------------- #
# adapters -> [(order, heading, body)]
# --------------------------------------------------------------------------- #
def _apply_marks(book: dict, body: str, boundary: re.Pattern,
                 chapters: list[tuple[str, str]]) -> tuple[list, list]:
    """Pull front/back matter out of a Gutenberg text into its own chapters.

    Front matter sits between the end of the CONTENTS block and the first real
    chapter heading (Middlemarch's PRELUDE), so the mark is searched in the whole
    body from its *last* occurrence — the first one is the contents listing — and
    the text runs to the next chapter boundary. Back matter trails the last
    chapter's body (FINALE, Epilogue).
    """
    front: list[tuple[int, str, str]] = []
    for spec in book.get("front_marks") or []:
        marks = list(re.finditer(spec["mark"], body, re.M))
        if not marks:
            print(f"   ! front mark not found: {spec['heading']}")
            continue
        start = marks[-1].start()
        nxt = boundary.search(body, start + 1)
        chunk = body[start: nxt.start() if nxt else len(body)].strip()
        front.append((0, spec["heading"], clean.clean_paragraphs(chunk)))

    back: list[tuple[int, str, str]] = []
    if chapters:
        head, text = chapters[-1]
        for spec in book.get("back_marks") or []:
            marks = list(re.finditer(spec["mark"], text, re.M))
            if not marks:
                print(f"   ! back mark not found: {spec['heading']}")
                continue
            cut = marks[-1].start()
            tail = text[cut:].rstrip() + "\n"
            text = text[:cut].rstrip() + "\n"
            back.append((0, spec["heading"], tail))
        chapters[-1] = (head, text)
    return front, back


def fetch_gutenberg(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    text = http_text(book["source_url"], timeout=120)
    body = clean.strip_pg_boilerplate(text)
    boundary = re.compile(book.get("chapter_re", r"^BOOK\s+[IVXLC]+$"), re.M)
    _preamble, chapters = clean.clean_to_chapters(body, boundary)
    if not chapters:
        raise SystemExit(f"{book['slug']}: no chapters matched chapter_re")
    # Gutenberg files repeat every chapter heading in a CONTENTS block, so each
    # heading matches twice: once in the TOC (empty body) and once as the real
    # chapter. Keep the last occurrence of each heading.
    first_seen: dict[str, int] = {}
    for i, (h, _b) in enumerate(chapters):
        first_seen.setdefault(h, i)
    if len(first_seen) < len(chapters):
        last: dict[str, int] = {}
        for i, (h, _b) in enumerate(chapters):
            last[h] = i
        chapters = [chapters[i] for i in sorted(last.values())]
    front, back = _apply_marks(book, body, boundary, chapters)
    numbered = [
        (i, heading.strip().rstrip("."), text)
        for i, (heading, text) in enumerate(chapters, 1)
    ]
    if limit:
        numbered = numbered[:limit]
    return front + numbered + back


_PREFETCH: dict[str, str] = {}
API_BATCH = 50  # MediaWiki caps titles= at 50 per query


def _norm(title: str) -> str:
    return title.replace("_", " ").strip()


def prefetch_titles(titles: list[str], delay: float = 0.2) -> None:
    """Bulk-fetch raw wikitext, 50 titles per request.

    One action=raw per page costs a full round trip (~0.7 s); the query API
    returns 50 revisions per request (~0.05 s/page), which is the difference
    between minutes and seconds for a 300-poem anthology.
    """
    todo: list[str] = []
    seen = set()
    for t in titles:
        k = _norm(t)
        if k not in _PREFETCH and k not in seen:
            seen.add(k)
            todo.append(t)
    for i in range(0, len(todo), API_BATCH):
        chunk = todo[i:i + API_BATCH]
        q = {
            "action": "query", "prop": "revisions", "rvprop": "content",
            "rvslots": "main", "format": "json", "formatversion": "2",
            "titles": "|".join(chunk),
        }
        url = f"https://zh.wikisource.org/w/api.php?" + urllib.parse.urlencode(q)
        try:
            data = json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=90).read().decode())
        except Exception as e:  # noqa: BLE001
            print(f"   prefetch batch failed ({e}); falling back to per-page")
            continue
        for page in data.get("query", {}).get("pages", []):
            revs = page.get("revisions")
            if revs:
                _PREFETCH[_norm(page["title"])] = revs[0]["slots"]["main"]["content"]
        time.sleep(delay)


def fetch_wikitext(title: str, hops: int = 3) -> str:
    """Fetch raw wikitext, following #REDIRECT stubs."""
    raw = _PREFETCH.get(_norm(title))
    if raw is None:
        raw = _PREFETCH.get(_norm(title).replace(" ", "_"))
    if raw is None:
        url = f"{WIKISOURCE_API}?" + urllib.parse.urlencode({"action": "raw", "title": title})
        raw = http_text(url)
    for _ in range(hops):
        m = re.match(r"\s*#REDIRECT\s*\[\[\s*([^\]|#]+)", raw, re.I)
        if not m:
            break
        target = m.group(1).strip()
        print(f"   redirect: {title} -> {target}")
        title = target
        raw = _PREFETCH.get(_norm(title))
        if raw is None:
            url = f"{WIKISOURCE_API}?" + urllib.parse.urlencode({"action": "raw", "title": title})
            raw = http_text(url)
    return raw

def _extra_pages(book: dict, key: str) -> list[tuple[int, str, str]]:
    """Front/back matter: pages that are not part of the numbered sequence.

    They are written without a numeric filename prefix and carry order 0.
    """
    out: list[tuple[int, str, str]] = []
    for spec in book.get(key) or []:
        page = spec["page"] if isinstance(spec, dict) else spec
        heading = (spec.get("heading") if isinstance(spec, dict) else None) or page
        raw = fetch_wikitext(f"{book['source_id']}/{page}")
        profile = book.get("profile", "wikisource-novel")
        derived = wikisource_title(raw, profile) or heading
        body = wikitext_body(raw)
        # Some pages repeat their own title as the first line (續筆談).
        first, _, rest = body.partition("\n\n")
        if first.strip() == derived.strip() and rest.strip():
            body = rest
        if not body.strip():
            raise SystemExit(f"{book['slug']}: {key} page '{page}' produced no body")
        out.append((0, heading, body))
        time.sleep(float(book.get("delay_s", 0.4)))
    return out


def header_field(raw: str, key: str) -> str:
    hb = header_block(raw)
    if not hb:
        return ""
    m = re.search(rf"\|\s*{key}\s*=\s*(.*?)(?=\n\s*\||\Z)", hb, re.S)
    return _clean_title(m.group(1)) if m else ""


def _fetch_poem_index(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    """Anthologies whose source page is a TOC of links grouped by == 體裁 ==.

    唐詩三百首 is exactly this: the main page holds only the 蘅塘退士原序 prose
    plus 8 sections of poem links. One section becomes one chapter.
    """
    idx = http_text(
        f"{WIKISOURCE_API}?"
        + urllib.parse.urlencode({"action": "raw", "title": book["source_id"]})
    )
    sections: list[dict] = []
    cur: dict | None = None
    for line in idx.splitlines():
        stripped = line.strip()
        m = re.match(r"^==\s*([^=]+?)\s*==\s*$", stripped)
        if m:
            cur = {"name": m.group(1).strip(), "items": [], "text": []}
            sections.append(cur)
            continue
        if cur is None:
            continue
        lm = re.match(r"^#\s*([^\[]*)\[\[([^|\]]+)(?:\|([^\]]*))?\]\](.*)$", stripped)
        if lm:
            sub = re.search(r"<sub>(.*?)</sub>", lm.group(4) or "")
            cur["items"].append((
                lm.group(2).strip(),
                (lm.group(3) or lm.group(2)).strip(),
                lm.group(1).strip(),
                sub.group(1).strip() if sub else "",
            ))
        elif stripped:
            cur["text"].append(stripped)

    if not sections:
        raise SystemExit(f"{book['slug']}: no == sections == found on {book['source_id']}")
    if limit:
        sections = sections[:limit]

    prefetch_titles(
        [item[0] for sec in sections for item in sec["items"]],
        float(book.get("delay_s", 0.2)),
    )
    out: list[tuple[int, str, str]] = []
    for n, sec in enumerate(sections, 1):
        if not sec["items"]:
            prose = wikitext_body("\n".join(sec["text"]))
            if len(prose) < int(book.get("min_chars", 150)):
                continue
            out.append((n, sec["name"], prose))
            continue
        chunks: list[str] = []
        for target, disp, author, sub in sec["items"]:
            raw = fetch_wikitext(target)
            poem = wikitext_body(raw)
            if len(poem.strip()) < 8:
                print(f"   ! empty poem, skipped: {target}")
                continue
            who = header_field(raw, "author") or author
            heading = disp + (f"（{sub}）" if sub else "")
            chunks.append(f"【{heading}】" + (f"　{who}" if who else "") + "\n\n" + poem.strip())
            time.sleep(float(book.get("delay_s", 0.2)))
        body = "\n\n".join(chunks) + "\n"
        if len(body) < int(book.get("min_chars", 150)):
            raise SystemExit(f"{book['slug']}: section '{sec['name']}' too short ({len(body)})")
        out.append((n, sec["name"], body))
    return out


HEAD_LINE_RE = re.compile(r"^==\s*(.+?)\s*==\s*$")
AUTHOR_IN_HEAD_RE = re.compile(r"[（(]\s*\[\[\s*(?:Author|作者)\s*:\s*([^|\]]+)(?:\|([^\]]*))?\]\]\s*[)）]")
TRANSCLUDE_RE = re.compile(r"^\{\{:\s*([^}|]+?)\s*\}\}\s*$", re.M)
SINGLE_QUOTE3 = "'" * 3


def _fetch_split_poems(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    """One page holding a whole anthology, each poem under =='''詞牌'''（作者）==.

    宋詞三百首 is this shape (no subpages, no link TOC). Poems are grouped by
    poet into one chapter each, preserving the anthology's own order: ~300
    individual chapters would collide (晏殊 has three 木蘭花).
    """
    raw = fetch_wikitext(book["source_id"])
    entries: list[dict] = []
    cur: dict | None = None
    for ln in raw.splitlines():
        m = HEAD_LINE_RE.match(ln.strip())
        if m:
            head = m.group(1)
            am = AUTHOR_IN_HEAD_RE.search(head)
            author = (am.group(2) or am.group(1)).strip() if am else ""
            title = (head[: am.start()] if am else head).replace(SINGLE_QUOTE3, "").strip()
            title = LINK_RE.sub(r"\1", title).strip()
            if not title:
                cur = None
                continue
            cur = {"title": title, "author": author, "lines": []}
            entries.append(cur)
            continue
        if cur is not None:
            cur["lines"].append(ln)

    # {{:頁名}} transcludes the poem from its own page (青玉案 辛棄疾)
    for e in entries:
        blob = "\n".join(e["lines"])
        tm = TRANSCLUDE_RE.search(blob)
        if tm and len(re.sub(r"\s", "", blob)) < 60:
            fetched = fetch_wikitext(tm.group(1).strip())
            e["lines"] = fetched.splitlines()
            # Heading was ==[[青玉案 (辛棄疾)]]==: no （作者） to parse, so take the
            # author from the transcluded page and trim the parenthetical title.
            if not e["author"]:
                e["author"] = header_field(fetched, "author")
            pm = re.search(r"[（(]([^)）]+)[)）]\s*$", e["title"])
            if pm:
                if not e["author"]:
                    e["author"] = pm.group(1).strip()
                e["title"] = e["title"][: pm.start()].strip() or e["title"]
        e["body"] = wikitext_body("\n".join(e["lines"]))

    groups: list[tuple[str, list[dict]]] = []
    for e in entries:
        if not e["body"].strip():
            print(f"   ! empty poem: {e['title']} ({e['author']})")
            continue
        if groups and groups[-1][0] == e["author"]:
            groups[-1][1].append(e)
        else:
            groups.append((e["author"], [e]))
    if not groups:
        raise SystemExit(f"{book['slug']}: no poems parsed from {book['source_id']}")
    if limit:
        groups = groups[:limit]

    out: list[tuple[int, str, str]] = []
    for n, (author, items) in enumerate(groups, 1):
        chunks = [f"【{e['title']}】\n\n{e['body'].strip()}" for e in items]
        body = "\n\n".join(chunks) + "\n"
        out.append((n, author or "無名氏", body))
    return out


TOC_CHILD_RE = re.compile(r"^(\*{1,2})\s*\[\[\s*/?([^|\]]+?)(?:\|([^\]]*))?\]\]")


def _fetch_toc_groups(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    """Index page listing chapters (*) and their topics (**); one chapter per group.

    天工開物 is this shape: the 18 chapter pages hold only the 宋子曰 preface and
    the technique text lives in the topic pages listed beneath them. Shipping the
    chapter pages alone would give 18 prefaces and no book.
    """
    raw = fetch_wikitext(book["source_id"])
    groups: list[dict] = []
    for ln in raw.splitlines():
        stripped = ln.strip()
        m = TOC_CHILD_RE.match(stripped)
        if not m:
            continue
        page = m.group(2).strip()
        disp = (m.group(3) or page).strip()
        if page.endswith("自序") or page == "全覽":
            continue
        if m.group(1) == "**" and groups:
            groups[-1]["children"].append((page, disp))
        else:
            groups.append({"page": page, "disp": disp, "children": []})
    if not groups:
        raise SystemExit(f"{book['slug']}: no TOC entries found on {book['source_id']}")
    if limit:
        groups = groups[:limit]

    want: list[str] = []
    for g in groups:
        want.append(f"{book['source_id']}/{g['page']}")
        want += [f"{book['source_id']}/{p}" for p, _ in g["children"]]
    prefetch_titles(want, float(book.get("delay_s", 0.2)))

    out: list[tuple[int, str, str]] = []
    for n, g in enumerate(groups, 1):
        parts: list[str] = []
        head = wikitext_body(fetch_wikitext(f"{book['source_id']}/{g['page']}")).strip()
        if head:
            parts.append(head)
        for page, disp in g["children"]:
            body = wikitext_body(fetch_wikitext(f"{book['source_id']}/{page}")).strip()
            if body:
                parts.append(f"【{disp}】\n\n{body}")
        body = "\n\n".join(parts) + "\n"
        if len(body) < int(book.get("min_chars", 150)):
            raise SystemExit(f"{book['slug']}: chapter '{g['disp']}' too short ({len(body)})")
        out.append((n, g["disp"], body))
        time.sleep(float(book.get("delay_s", 0.2)))
    return out


def _fetch_page_list(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    """Explicit ordered page list for books with no numeric 回/卷 sequence."""
    entries = list(book["pages"])
    if limit:
        entries = entries[:limit]
    want: list[str] = [
        f"{book['source_id']}/{(e['page'] if isinstance(e, dict) else e)}" for e in entries
    ]
    for key in ("front_pages", "back_pages"):
        want += [
            f"{book['source_id']}/{(e['page'] if isinstance(e, dict) else e)}"
            for e in (book.get(key) or [])
        ]
    prefetch_titles(want, float(book.get("delay_s", 0.2)))
    out: list[tuple[int, str, str]] = _extra_pages(book, "front_pages")
    for i, spec in enumerate(entries, 1):
        page = spec["page"] if isinstance(spec, dict) else spec
        heading = (spec.get("heading") if isinstance(spec, dict) else None) or page
        body = wikitext_body(fetch_wikitext(f"{book['source_id']}/{page}"))
        if len(body) < int(book.get("min_chars", 500)):
            raise SystemExit(f"{book['slug']}: page '{page}' unusable (chars={len(body)})")
        out.append((i, heading, body))
        time.sleep(float(book.get("delay_s", 0.4)))
    out.extend(_extra_pages(book, "back_pages"))
    return out


def fetch_wikisource(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    if book.get("poem_index"):
        return _fetch_poem_index(book, limit)
    if book.get("toc_groups"):
        return _fetch_toc_groups(book, limit)
    if book.get("split_poems"):
        return _fetch_split_poems(book, limit)
    if book.get("pages"):
        return _fetch_page_list(book, limit)
    total = int(book["chapter_total"])
    if limit:
        total = min(total, limit)
    profile = book.get("profile", "wikisource-novel")
    pattern = book.get("page_pattern") or "第{n:03d}回"
    prefetch_titles(
        [f"{book['source_id']}/{pattern.format(n=n)}" for n in range(1, total + 1)],
        float(book.get("delay_s", 0.2)),
    )
    out: list[tuple[int, str, str]] = []
    out.extend(_extra_pages(book, "front_pages"))
    for n in range(1, total + 1):
        raw = fetch_wikitext(f"{book['source_id']}/{pattern.format(n=n)}")
        heading = wikisource_title(raw, profile)
        body = wikitext_body(raw)
        if not heading or len(body) < int(book.get("min_chars", 500)):
            raise SystemExit(f"{book['slug']}: chapter {n} unusable (heading={heading!r}, chars={len(body)})")
        # Some profiles already carry the 第X回 / 卷N prefix in the heading; strip
        # it so the composed filename never doubles it. write_book() adds numbering.
        heading = CN_PREFIX_RE.sub("", heading).strip() or heading
        heading = CN_VOLUME_RE.sub("", heading).strip() or _body_heading(body) or heading
        out.append((n, heading, body))
        time.sleep(float(book.get("delay_s", 0.4)))
    out.extend(_extra_pages(book, "back_pages"))
    return out


def fetch_gutenberg_collection(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    """A set of independent Gutenberg texts, one chapter each.

    Used for Plato's dialogues: each is a separate ebook (pg1642, pg1656, …) and
    each deserves to be one chapter of a single collection rather than 26 books.
    """
    chunks: list[tuple[str, str]] = []
    for item in book["sources"]:
        text = http_text(item["url"], timeout=180)
        body = clean.strip_pg_boilerplate(text)
        # Drop the "Produced by …" credit, repeated title block and any Contents
        # list; start at Jowett's INTRODUCTION (or the dramatis personae).
        lines = body.splitlines()
        for i, ln in enumerate(lines):
            probe = ln.strip().strip(".").upper()
            if probe == "INTRODUCTION" or ln.strip().upper().startswith("PERSONS OF THE DIALOGUE"):
                lines = lines[i:]
                break
        cleaned = clean.clean_paragraphs("\n".join(lines))
        if len(cleaned) < int(book.get("min_chars", 500)):
            raise SystemExit(
                f"{book['slug']}: {item['title']} too short ({len(cleaned)} chars)"
            )
        chunks.append((item["title"], cleaned))
        time.sleep(float(book.get("delay_s", 1.0)))
    if limit:
        chunks = chunks[:limit]
    return [(i, title, body) for i, (title, body) in enumerate(chunks, 1)]


def fetch(book: dict, limit: int = 0) -> list[tuple[int, str, str]]:
    src = book["source"].lower()
    if src == "gutenberg":
        return fetch_gutenberg(book, limit)
    if src == "gutenberg_collection":
        return fetch_gutenberg_collection(book, limit)
    if src == "wikisource":
        return fetch_wikisource(book, limit)
    raise SystemExit(f"{book['slug']}: unknown source '{src}'")


# --------------------------------------------------------------------------- #
# write into staging
# --------------------------------------------------------------------------- #
def chapter_filename(book: dict, order: int, heading: str) -> str:
    """`第001回 標題.txt` for numbered units, plain `序.txt` for front/back matter."""
    if order <= 0:
        return safe_name(heading) + ".txt"
    if book.get("lang") == "zh":
        prefix = f"第{order:03d}{book.get('unit', '回')} "
    else:
        prefix = f"{order:02d} "
    return safe_name(prefix + heading) + ".txt"


def write_book(book: dict, chapters: list[tuple[int, str, str]], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    shas: dict[str, str] = {}
    names: list[str] = []
    for order, heading, body in chapters:
        name = chapter_filename(book, order, heading)
        (root / name).write_text(body, encoding="utf-8")
        names.append(name)
        shas[name] = hashlib.sha256(body.encode("utf-8")).hexdigest()

    book_file = book.get("book_file", book["title"])
    lines = [f"# {book['title']}", ""]
    if book.get("author"):
        note = book.get("index_note")
        if note is None:
            note = f"{book['chapter_total']} 回" if book.get("lang") == "zh" else ""
        lines += [f"{book['author']}" + (f" · {note}" if note else ""), ""]
    if book.get("source_url"):
        lines += [f"來源：{book.get('source', '')} — {book['source_url']}", ""]
    if book.get("license"):
        lines += [f"授權：{book['license']}", ""]
    if book.get("pd_basis"):
        lines += [book["pd_basis"], ""]
    lines += ["## 目錄" if book.get("lang") == "zh" else "## Contents", ""]
    for i, (order, heading, _body) in enumerate(chapters, 1):
        lines.append(f"{i:03d}. [{heading}](./{urllib.parse.quote(names[i-1], safe='')})")
    lines.append("")
    (root / f"{book_file}.md").write_text("\n".join(lines), encoding="utf-8")

    meta = {k: book[k] for k in
            ("title", "author", "translator", "year", "source", "source_url",
             "license", "pd_basis", "description") if book.get(k) not in (None, "")}
    meta["chapter_total"] = len(chapters)
    meta["chapters"] = shas
    (root / ".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# validators
# --------------------------------------------------------------------------- #
def _extras_count(book: dict) -> int:
    return (
        len(book.get("front_pages") or [])
        + len(book.get("back_pages") or [])
        + len(book.get("front_marks") or [])
        + len(book.get("back_marks") or [])
    )


def validate(book: dict, root: Path, expect: int = 0) -> list[str]:
    issues: list[str] = []
    files = sorted(root.glob("*.txt"))
    unit_re = re.compile(rf"^第(\d{{3}}){re.escape(book.get('unit', '回'))}\s*(.*)$")
    want = expect or (int(book.get("chapter_total", 0) or 0) + _extras_count(book))
    if want and len(files) != want:
        issues.append(f"#1 chapter count: expected {want}, found {len(files)}")

    min_chars = int(book.get("min_chars", 500))
    max_chars = int(book.get("max_chars", 400000))
    orders: list[int] = []
    bodies: dict[str, str] = {}
    headings: list[str] = []
    for p in files:
        text = p.read_text(encoding="utf-8")
        m = unit_re.match(p.stem)
        if m:
            orders.append(int(m.group(1)))
            headings.append(m.group(2).strip())
        if "\ufffd" in text:
            issues.append(f"#6 U+FFFD in {p.name}")
        if not (min_chars <= len(text) <= max_chars):
            issues.append(f"#4 size out of band ({len(text)}): {p.name}")
        residual = RESIDUAL_RE.search(text)
        if residual:
            issues.append(f"#3 residual wikitext '{residual.group(0)}' in {p.name}")
        for ln in text.splitlines():
            if ln[:1] in (":", "*", "=") and ln.strip():
                issues.append(f"#3 line starts with '{ln[0]}' in {p.name}")
                break
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in bodies:
            issues.append(f"#8 duplicate body: {p.name} == {bodies[digest]}")
        bodies[digest] = p.name
        if book.get("lang") == "zh":
            cjk = len(CJK_RE.findall(text))
            if cjk / max(len(text), 1) < 0.12:
                issues.append(f"#5 CJK ratio too low in {p.name}")
        else:
            if sum(c.isalpha() for c in text) / max(len(text), 1) < 0.4:
                issues.append(f"#5 Latin ratio too low in {p.name}")

    if orders != sorted(orders) or (orders and sorted(orders) != list(range(1, len(orders) + 1))):
        issues.append(f"#7 chapter numbering not 1..N contiguous ({orders[:5]}…)")
    if any(not h for h in headings):
        issues.append("#2 empty chapter heading")
    doubled = [h for h in headings if re.match(r"^第\s*[0-9]+\s*回", h)]
    if doubled:
        issues.append(f"#2 heading repeats the chapter number ({doubled[0][:24]})")

    index = next(iter(root.glob("*.md")), None)
    if not index:
        issues.append("#10 index .md missing")
    else:
        links = re.findall(r"\]\(\./([^)]+)\)", index.read_text(encoding="utf-8"))
        if want and len(links) != want:
            issues.append(f"#10 index links {len(links)} != {want}")
        for link in links:
            if not (root / urllib.parse.unquote(link)).exists():
                issues.append(f"#10 index link missing on disk: {link}")

    meta_p = root / ".meta.json"
    if not meta_p.exists():
        issues.append("#9 .meta.json missing")
    else:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        recorded = meta.get("chapters") or {}
        if len(recorded) != len(files):
            issues.append(f"#9 sha256 map has {len(recorded)} entries for {len(files)} files")
    return issues


# --------------------------------------------------------------------------- #
# promote
# --------------------------------------------------------------------------- #
def promote(book: dict, staging: Path) -> Path:
    target = CONTENT / book["category"] / book["slug"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        old = STAGING / f".old-{book['slug']}"
        if old.exists():
            shutil.rmtree(old)
        target.rename(old)
        staging.rename(target)
        shutil.rmtree(old, ignore_errors=True)
    else:
        staging.rename(target)
    return target


def _rel(p: Path) -> Path | str:
    """Path relative to the repo when possible (tmp dirs in tests are not)."""
    try:
        return p.relative_to(REPO)
    except ValueError:
        return p


def write_report(book: dict, staging: Path, issues: list[str]) -> Path:
    path = staging / "REPORT.md"
    lines = [f"# Validation failed: {book['title']} ({book['slug']})", "",
             f"checks failed: {len(issues)}", "", "## Issues", ""]
    lines += [f"- {i}" for i in issues[:200]]
    if len(issues) > 200:
        lines.append(f"- … +{len(issues) - 200} more")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_ingest(book: dict, dry_run: bool, limit: int) -> int:
    total = int(book.get("chapter_total", 0) or 0)
    if dry_run:
        print(f"[dry-run] {book['slug']}: would fetch {total or '?'} chapters "
              f"from {book['source']} into {book['category']}/{book['slug']}")
        return 0
    print(f"== {book['title']} ({book['slug']}): fetching {total or '?'} chapters")
    try:
        chapters = fetch(book, limit)
    except (RuntimeError, SystemExit, OSError) as e:
        print(f"   FAILED fetch: {e} — nothing promoted, content/ untouched")
        return 1

    staging = STAGING / book["slug"]
    if staging.exists():
        shutil.rmtree(staging)
    write_book(book, chapters, staging)
    print(f"   staging: {len(chapters)} chapters written")

    issues = validate(book, staging, expect=(limit + _extras_count(book)) if limit else 0)
    if not issues and limit:
        print(f"   drill OK -> staging kept at {_rel(staging)} (--limit never promotes)")
        return 0
    if issues:
        rep = write_report(book, staging, issues)
        print(f"   FAILED {len(issues)} checks -> {_rel(rep)}")
        for i in issues[:10]:
            print(f"     {i}")
        return 1
    target = promote(book, staging)
    print(f"   OK -> {_rel(target)} ({len(chapters)} chapters, all checks green)")
    return 0


def cmd_reindex(book: dict) -> int:
    target = CONTENT / book["category"] / book["slug"]
    if not target.exists():
        raise SystemExit(f"{book['slug']}: nothing on disk at {target}")
    files = sorted(target.glob("*.txt"))
    chapters = []
    unit_re = re.compile(rf"^第(\d{{3}}){re.escape(book.get('unit', '回'))}\s*(.*)$")
    for p in files:
        m = unit_re.match(p.stem) or re.match(r"^(\d+)[ .](.*)$", p.stem)
        order = int(m.group(1)) if m else 0
        chapters.append((order, m.group(2) if m else p.stem, p.read_text(encoding="utf-8")))
    chapters.sort(key=lambda c: (c[0] == 0, c[0]))
    write_book(book, chapters, target)
    issues = validate(book, target)
    print(f"   reindexed {len(chapters)} chapters, {len(issues)} issues")
    for i in issues[:10]:
        print(f"     {i}")
    return 1 if issues else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", help="slug from scripts/books.toml")
    ap.add_argument("--all", action="store_true", help="every book in the registry")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N chapters")
    ap.add_argument("--reindex", action="store_true", help="offline: rebuild index/.meta from disk")
    ap.add_argument("--validate-only", action="store_true", help="validate content/ without fetching")
    ap.add_argument("--registry", default=str(REGISTRY))
    args = ap.parse_args()

    registry = load_registry(Path(args.registry))
    if args.all:
        slugs = list(registry)
    elif args.book:
        if args.book not in registry:
            raise SystemExit(f"unknown book '{args.book}' (known: {', '.join(registry)})")
        slugs = [args.book]
    else:
        raise SystemExit("pass --book <slug> or --all")

    rc = 0
    for slug in slugs:
        book = registry[slug]
        if args.validate_only:
            target = CONTENT / book["category"] / book["slug"]
            issues = validate(book, target) if target.exists() else [f"missing target {target}"]
            print(f"{slug}: {len(issues)} issues")
            for i in issues[:20]:
                print(f"   {i}")
            rc |= 1 if issues else 0
        elif args.reindex:
            rc |= cmd_reindex(book)
        else:
            rc |= cmd_ingest(book, args.dry_run, args.limit)
    return rc


if __name__ == "__main__":
    sys.exit(main())
