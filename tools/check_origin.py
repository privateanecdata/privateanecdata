#!/usr/bin/env python3
"""
Fail if any page on the running site references anything from another origin, or carries any
script at all. This is the enforcement behind "your browser's network panel should show one
host." Run it against a built server; tools/check_origin.sh does the build-start-check-stop.

    python3 tools/check_origin.py http://127.0.0.1:4321 [--max-pages 500]

Checks every reachable HTML page (same-origin links, breadth-first), every stylesheet, and every
SVG the pages reference. A `<script>` element anywhere, or any src/href/url() that resolves to
another origin (including protocol-relative and data: for scripts), is a failure.
"""
import argparse
import re
import sys
import urllib.parse
import urllib.request
from collections import deque

# Every element that can fetch, and every attribute on it that can carry a URL — quoted or not,
# all of them, not just the first. <base> and <meta refresh> can redirect subresources or the page.
ELEMENT = re.compile(r'<(link|img|iframe|object|embed|video|audio|source|track|image|use|base|meta|form|a)\b([^>]*)>', re.I)
URL_ATTR = re.compile(r'\s(src|href|xlink:href|data|poster|srcset|action|content|formaction|ping)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.I)
SCRIPT = re.compile(r'<script\b', re.I)
INLINE_HANDLER = re.compile(r'\son[a-z]+\s*=', re.I)
STYLE_BLOCK = re.compile(r'<style\b[^>]*>(.*?)</style>|\sstyle\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I | re.S)
CSS_URL = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)|@import\s+(?:url\()?["\']?([^"\')\s;]+)', re.I)


def url_attrs(html):
    """Yield (tag, attr, value) for every URL-carrying attribute of every fetching element."""
    for m in ELEMENT.finditer(html):
        tag, attrs = m.group(1).lower(), m.group(2)
        # A canonical/alternate <link> names a URL; it does not fetch one.
        if tag == 'link' and re.search(r'\srel\s*=\s*["\']?(canonical|alternate)\b', attrs, re.I):
            continue
        for a in URL_ATTR.finditer(attrs):
            name = a.group(1).lower()
            value = a.group(2) if a.group(2) is not None else a.group(3) if a.group(3) is not None else a.group(4)
            if tag == 'meta':
                if name == 'content' and re.search(r'http-equiv\s*=\s*["\']?refresh', attrs, re.I):
                    url = re.search(r'url\s*=\s*["\']?([^"\';]+)', value or '', re.I)
                    if url:
                        yield tag, 'refresh', url.group(1).strip()
                continue
            if name == 'content':
                continue
            if name == 'srcset':
                for cand in value.split(','):
                    if cand.strip():
                        yield tag, name, cand.strip().split()[0]
            else:
                yield tag, name, value


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "check_origin"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace"), dict(r.headers)


def same_origin(base, ref):
    if ref.startswith(("data:", "mailto:", "#")):
        return True
    u = urllib.parse.urljoin(base, ref)
    b, r = urllib.parse.urlsplit(base), urllib.parse.urlsplit(u)
    return (r.scheme, r.netloc) == (b.scheme, b.netloc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("origin")
    ap.add_argument("--max-pages", type=int, default=500)
    args = ap.parse_args()
    origin = args.origin.rstrip("/")
    seen, queue, failures, pages, assets = set(), deque(["/"]), [], 0, 0
    while queue and pages + assets < args.max_pages:
        path = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        url = origin + path
        try:
            status, ctype, body, headers = fetch(url)
        except Exception as e:
            failures.append(f"{path}: fetch failed ({e})")
            continue
        if "text/html" in ctype:
            pages += 1
            if not any(k.lower() == "content-security-policy" for k in headers):
                failures.append(f"{path}: no Content-Security-Policy header")
            if SCRIPT.search(body):
                failures.append(f"{path}: <script> element present")
            if INLINE_HANDLER.search(body):
                failures.append(f"{path}: inline event handler present")
            for tag, attr, ref in url_attrs(body):
                if tag == 'base':
                    failures.append(f"{path}: <base href> present: {ref}")
                elif tag == 'a' and attr == 'href':
                    if same_origin(url, ref) and not ref.startswith(("mailto:", "#")):
                        p = urllib.parse.urlsplit(urllib.parse.urljoin(url, ref)).path
                        if p not in seen:
                            queue.append(p)
                elif tag == 'a':
                    failures.append(f"{path}: <a {attr}> present: {ref}")
                elif tag == 'form':
                    if not same_origin(url, ref):
                        failures.append(f"{path}: form posts to another origin: {ref}")
                elif not same_origin(url, ref):
                    failures.append(f"{path}: {tag} {attr} from another origin: {ref}")
                elif re.search(r"\.(css|svg)(\?|$)", ref):
                    queue.append(urllib.parse.urlsplit(urllib.parse.urljoin(url, ref)).path)
            for m in STYLE_BLOCK.finditer(body):
                css = m.group(1) or m.group(2) or m.group(3) or ''
                for a, b in CSS_URL.findall(css):
                    ref = a or b
                    if ref and not same_origin(url, ref):
                        failures.append(f"{path}: inline CSS url() from another origin: {ref}")
        elif "text/css" in ctype or "image/svg" in ctype:
            assets += 1
            for a, b in CSS_URL.findall(body):
                ref = a or b
                if ref and not same_origin(url, ref):
                    failures.append(f"{path}: url() from another origin: {ref}")
            if "image/svg" in ctype:
                if SCRIPT.search(body) or INLINE_HANDLER.search(body):
                    failures.append(f"{path}: script in SVG")
                for tag, attr, ref in url_attrs(body):
                    if not same_origin(url, ref):
                        failures.append(f"{path}: SVG {tag} {attr} references another origin: {ref}")
    print(f"checked {pages} pages and {assets} stylesheets/figures from {origin}")
    for f in failures:
        print("  FAIL", f)
    print("RESULT:", "FAILED" if failures else "one origin, no scripts")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
