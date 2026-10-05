"""On-page audit of the built static site (no network needed).

Collects the signals the agent can change and flags clear problems, so each
experiment starts from a known baseline.
"""

import json
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_description = None
        self.canonical = None
        self.h1 = 0
        self.links = []
        self.jsonld_raw = []
        self.words = 0
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._stack.append((tag, a))
        if tag == "meta" and a.get("name") == "description":
            self.meta_description = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        while self._stack:
            if self._stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if not self._stack:
            return
        tag, attrs = self._stack[-1]
        if tag == "title":
            self.title += data
        elif tag == "script" and attrs.get("type") == "application/ld+json":
            self.jsonld_raw.append(data)
        elif tag not in ("script", "style"):
            self.words += len(data.split())


@dataclass
class PageAudit:
    path: str          # URL path, e.g. /cron/every-5-minutes/
    title: str
    title_len: int
    meta_len: int
    h1_count: int
    words: int
    internal_out: int
    internal_in: int = 0
    jsonld_types: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def url_path(root, file):
    rel = file.relative_to(root).as_posix()
    if rel.endswith("index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def _normalise(href):
    href = href.split("#")[0].split("?")[0]
    if href.startswith("https://vip-ul.codes"):
        href = href[len("https://vip-ul.codes"):] or "/"
    return href if href.startswith("/") else None


def audit_site(root, site="https://vip-ul.codes"):
    root = Path(root)
    files = [p for p in root.rglob("*.html")
             if not any(part.startswith(".") or part in ("tests", "generator", "seo_agent")
                        for part in p.relative_to(root).parts)]
    pages = {}
    outlinks = {}
    for f in sorted(files):
        p = _PageParser()
        p.feed(f.read_text())
        path = url_path(root, f)
        internal = {n for n in (_normalise(h) for h in p.links) if n and n != path}
        outlinks[path] = internal
        types, issues = [], []
        for raw in p.jsonld_raw:
            try:
                types.append(json.loads(raw).get("@type"))
            except json.JSONDecodeError:
                issues.append("invalid JSON-LD")
        title = " ".join(p.title.split())
        meta = p.meta_description or ""
        if not title:
            issues.append("missing title")
        elif len(title) > 65:
            issues.append(f"title is {len(title)} chars (may be truncated in results)")
        if not meta:
            issues.append("missing meta description")
        elif not 70 <= len(meta) <= 165:
            issues.append(f"meta description is {len(meta)} chars")
        if p.h1 != 1:
            issues.append(f"{p.h1} <h1> elements")
        if p.canonical != site + path and not (path.endswith(".html") and p.canonical == site + path[:-5]):
            issues.append(f"canonical {p.canonical!r} does not match {site + path}")
        pages[path] = PageAudit(path, title, len(title), len(meta), p.h1, p.words,
                                len(internal), jsonld_types=types, issues=issues)

    def resolve(link):
        if link in pages:
            return link
        for cand in (link + ".html", link.rstrip("/") + "/", link.removesuffix(".html")):
            if cand in pages:
                return cand
        return None

    for src, links in outlinks.items():
        for link in links:
            target = resolve(link)
            if target:
                pages[target].internal_in += 1
            elif not link.startswith(("/css/", "/js/")):
                pages[src].issues.append(f"broken internal link {link}")

    sitemap = root / "sitemap.xml"
    listed = set()
    if sitemap.exists():
        text = sitemap.read_text()
        listed = {_normalise(chunk.split("</loc>")[0]) for chunk in text.split("<loc>")[1:]}
    for path, page in pages.items():
        if path not in listed and path != "/404.html":
            page.issues.append("not in sitemap.xml")
        if page.internal_in == 0 and path != "/":
            page.issues.append("orphan page (no internal links point to it)")
    return list(pages.values())
