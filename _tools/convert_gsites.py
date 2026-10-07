"""Convert the legacy Google Sites pages of fredasongdrechsler.com into Quarto .qmd files.

Prose and code are carried over verbatim; only markup changes. Images are downloaded
immediately after each page fetch because Google Sites image URLs are short-lived.

Usage: python3 _tools/convert_gsites.py [page ...]   (default: all pages in PAGES)
"""
import html
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://www.fredasongdrechsler.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0"}

# Google Sites path -> qmd path (relative to ROOT). URLs are preserved on GitHub Pages.
PAGES = {
    "fun-stuff": "fun-stuff.qmd",
    "intro-to-python-for-fnce": "intro-to-python-for-fnce/index.qmd",
    "intro-to-python-for-fnce/maneuvering-wrds-data": "intro-to-python-for-fnce/maneuvering-wrds-data.qmd",
    "intro-to-python-for-fnce/sp500-constituents": "intro-to-python-for-fnce/sp500-constituents.qmd",
    "intro-to-python-for-fnce/exchange-rate": "intro-to-python-for-fnce/exchange-rate.qmd",
    "data-crunching/connect-wrds": "data-crunching/connect-wrds.qmd",
    "data-crunching/fama-french": "data-crunching/fama-french.qmd",
    "data-crunching/dgtw": "data-crunching/dgtw.qmd",
    "data-crunching/iclink": "data-crunching/iclink.qmd",
    "data-crunching/pead": "data-crunching/pead.qmd",
    "data-crunching/io_breadth": "data-crunching/io_breadth.qmd",
    "textual-analysis": "textual-analysis/index.qmd",
    "textual-analysis/wrds-sec": "textual-analysis/wrds-sec.qmd",
    "textual-analysis/textual-analysis-on-sp500-companies": "textual-analysis/textual-analysis-on-sp500-companies.qmd",
    "web-scraping": "web-scraping/index.qmd",
    "web-scraping/european-short-position-data": "web-scraping/european-short-position-data.qmd",
}
# Display titles where the Google Sites heading was a slug; body text is untouched.
TITLES = {
    "data-crunching/connect-wrds": "Connecting to WRDS",
    "data-crunching/fama-french": "Fama–French 3-Factor Model",
    "data-crunching/dgtw": "Characteristics-Based Benchmarks (DGTW)",
    "data-crunching/iclink": "Linking IBES and CRSP (ICLINK)",
    "data-crunching/pead": "Post-Earnings Announcement Drift",
    "textual-analysis/wrds-sec": "WRDS SEC",
}
# Pages rebuilt by hand; linked to but never regenerated.
ALL_TARGETS = {**PAGES, "cv": "cv.qmd", "home": "index.qmd", "": "index.qmd",
               "data-crunching": "data-crunching/index.qmd",
               "data-crunching/momentum": "data-crunching/momentum.qmd"}

BLOCK = re.compile(
    r'data-code="(?P<code>[^"]*)"'
    r'|<img[^>]*src="(?P<img>https://lh\d[^"]+)"'
    r'|<(?P<tag>h1|h2|h3|h4|p|li)\b[^>]*>(?P<body>.*?)</(?P=tag)>',
    re.S,
)
PY_HINT = re.compile(r"(^|\n)\s*(import |from |def |class |for |if |print\(|#)|=|\w\(")


def fetch(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def unwrap(href):
    href = html.unescape(href)
    if "google.com/url" in href:
        href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)["q"][0]
    return href


def rel_link(href, here_qmd):
    """Map an internal Google Sites path to a relative .qmd link."""
    path = href.split("#")[0].strip("/")
    target = ALL_TARGETS.get(path)
    if target is None:
        return href
    return os.path.relpath(target, os.path.dirname(here_qmd) or ".")


def inline(fragment, here_qmd):
    """Google Sites inline HTML -> Markdown (links, bold, italic)."""
    def a(m):
        text = inline_text(m.group(2))
        href = unwrap(m.group(1))
        if href.startswith("#"):  # Google Sites heading anchors
            return text
        if href.startswith("/"):
            href = rel_link(href, here_qmd)
        return f"[{text}]({href})" if text.strip() else ""

    s = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', a, fragment, flags=re.S)
    s = re.sub(r"<strong>(.*?)</strong>", lambda m: f"**{m.group(1).strip()}**" if m.group(1).strip() else "", s, flags=re.S)
    s = re.sub(r'<span[^>]*font-style: ?italic[^>]*>(.*?)</span>',
               lambda m: f"*{m.group(1).strip()}*" if m.group(1).strip() else "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "  \n", s)
    return inline_text(s)


def inline_text(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", s).strip()


def code_text(attr):
    inner = html.unescape(attr)
    if inner.lstrip().startswith("<iframe"):
        return None, inner
    t = re.sub(r"<br\s*/?>", "\n", inner)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    return t.strip("\n"), None


def buttons(main):
    """Google Sites button blocks: aria-label text -> href of the anchor that follows."""
    out = {}
    for m in re.finditer(r'aria-label="([^"]+)"[^>]*data-tooltip="[^"]*".{0,1500}?href="([^"]+)"', main, re.S):
        out[html.unescape(m.group(1))] = unwrap(m.group(2))
    return out


def convert(path, qmd):
    raw = fetch(f"{SITE}/{path}").decode("utf-8")
    main = raw[raw.find('role="main"'):]
    main = main[: main.find("Report abuse")] if "Report abuse" in main else main
    btn = buttons(main)
    slug = path.replace("/", "_")
    img_dir = os.path.join(ROOT, "images", slug)
    n_img = 0
    title = None
    out = []
    for m in BLOCK.finditer(main):
        if m.group("code") is not None:
            code, iframe = code_text(m.group("code"))
            if iframe:
                out.append(f"```{{=html}}\n{iframe.strip()}\n```")
            elif code.strip():
                lang = "python" if PY_HINT.search(code) else "text"
                out.append(f"```{lang}\n{code.rstrip()}\n```")
        elif m.group("img"):
            n_img += 1
            os.makedirs(img_dir, exist_ok=True)
            data = fetch(html.unescape(m.group("img")))
            ext = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png"
            name = f"{n_img}{ext}"
            open(os.path.join(img_dir, name), "wb").write(data)
            src = os.path.relpath(os.path.join("images", slug, name), os.path.dirname(qmd) or ".")
            out.append(f"![]({src})")
        else:
            tag, body = m.group("tag"), m.group("body")
            plain = inline_text(body)
            if not plain:
                continue
            if plain in btn:  # button label rendered as its own paragraph
                href = btn[plain]
                if href.startswith("/"):  # raw HTML is not rewritten by Quarto: link the .html
                    href = rel_link(href, qmd).replace(".qmd", ".html")
                out.append(f'<div class="btn-row"><a class="primary" href="{href}">{plain}</a></div>')
                continue
            text = inline(body, qmd)
            if tag == "h1" and title is None:
                title = plain
            elif tag in ("h1", "h2"):
                out.append(f"## {text}")
            elif tag in ("h3", "h4"):
                out.append(f"### {text}")
            elif tag == "li":
                out.append(f"- {text}")
            else:
                out.append(text)
    # Join, keeping consecutive list items together.
    body = ""
    for i, block in enumerate(out):
        sep = "\n" if i and block.startswith("- ") and out[i - 1].startswith("- ") else "\n\n"
        body += (sep if i else "") + block
    title = (TITLES.get(path) or title or path.split("/")[-1]).replace('"', '\\"')
    dest = os.path.join(ROOT, qmd)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        f.write(f'---\ntitle: "{title}"\n---\n\n{body}\n')
    return title, n_img, sum(b.startswith("```") for b in out)


if __name__ == "__main__":
    for p in sys.argv[1:] or PAGES:
        t, ni, nc = convert(p, PAGES[p])
        print(f"{PAGES[p]:60s} {ni:2d} images {nc:2d} code  {t}")
