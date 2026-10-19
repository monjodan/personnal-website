#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown"]
# ///
"""Render writing/src/*.md into the essay pages, /writing/index.html, the
home-page essay list and /writing/feed.xml.  Run:  uv run writing/build.py

Front matter keys: title, date (YYYY-MM-DD), summary, slug, lead, alt.
Bracketed source markers like [arxiv.org] become visible placeholder links;
finished sources go in Markdown footnotes ([^1] ... [^1]: text), rendered as a Sources list."""
import datetime as dt
import html
import json
import pathlib
import re
from email.utils import format_datetime

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent
WRITING, TPL = ROOT / "writing", ROOT / "writing" / "templates"
SITE, AUTHOR = "https://jordanmonnet.com", "Jordan Monnet"
SEOUL = dt.timezone(dt.timedelta(hours=9))
SOURCE = r"\[([A-Za-z0-9.-]+)\](?!\()"


def fill(name, **ctx):
    tpl = (TPL / name).read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(ctx[m.group(1)]), tpl)


def long_date(d):
    return f"{d.day} {d:%B %Y}"


def load(path):
    head, body = re.match(r"^---\n(.*?)\n---\n(.*)$", path.read_text(encoding="utf-8"), re.S).groups()
    e = {k.strip(): v.strip().strip('"') for k, v in (l.split(":", 1) for l in head.splitlines() if ":" in l)}
    e["date"] = dt.date.fromisoformat(e["date"])
    e["url"] = f"{SITE}/writing/{e['slug']}/"
    e["media"] = e["lead"].rsplit("/", 1)[0]
    placeholder = lambda m: (f'<a class="source-todo" href="#">source: {m.group(1)}</a>'
                             f"<!-- TODO: add source URL for {m.group(1)} -->")
    e["html"] = re.sub(SOURCE, placeholder, markdown.markdown(body.strip(), extensions=["footnotes"]))
    return e


def render_essay(e):
    t, s, a = (html.escape(e[k]) for k in ("title", "summary", "alt"))
    og = f"{SITE}{e['media']}/og.jpg"
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "Article", "headline": e["title"],
        "description": e["summary"], "image": og, "datePublished": e["date"].isoformat(),
        "dateModified": e["date"].isoformat(), "inLanguage": "en", "mainEntityOfPage": e["url"],
        "author": {"@type": "Person", "name": AUTHOR, "url": f"{SITE}/"},
        "publisher": {"@type": "Person", "name": AUTHOR, "url": f"{SITE}/"},
    }, ensure_ascii=False, indent=2)
    content = fill("essay.html", title=t, iso_date=e["date"].isoformat(), date=long_date(e["date"]),
                   lead=e["lead"], alt=a, body=e["html"])
    page = fill("page.html", page_title=f"{t} — {AUTHOR}", description=s, url=e["url"], og_type="article",
                og_image=og, og_alt=a, content=content,
                jsonld=f'<script type="application/ld+json">\n{jsonld}\n</script>')
    out = WRITING / e["slug"] / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")


def card(e):  # /writing/ list entry
    return (f'<article class="essay-card reveal">\n'
            f'  <a class="essay-card-media" href="/writing/{e["slug"]}/" tabindex="-1" aria-hidden="true">'
            f'<img src="{e["media"]}/card.jpg" alt="" width="800" height="450" loading="lazy"></a>\n'
            f'  <div>\n    <div class="essay-date"><time datetime="{e["date"]}">{long_date(e["date"])}</time></div>\n'
            f'    <h2><a href="/writing/{e["slug"]}/">{html.escape(e["title"])}</a></h2>\n'
            f'    <p>{html.escape(e["summary"])}</p>\n  </div>\n</article>')


def row(e):  # home-page list entry
    return (f'        <article class="essay-row reveal">\n'
            f'          <div class="timeline-date"><time datetime="{e["date"]}">{long_date(e["date"])}</time></div>\n'
            f'          <div><h3><a href="/writing/{e["slug"]}/">{html.escape(e["title"])}</a></h3>'
            f'<p>{html.escape(e["summary"])}</p></div>\n        </article>')


def feed(essays):
    def item(e):
        when = format_datetime(dt.datetime.combine(e["date"], dt.time(9), SEOUL))
        return (f"  <item>\n    <title>{html.escape(e['title'])}</title>\n    <link>{e['url']}</link>\n"
                f'    <guid isPermaLink="true">{e["url"]}</guid>\n    <pubDate>{when}</pubDate>\n'
                f"    <description>{html.escape(e['summary'])}</description>\n"
                f'    <content:encoded><![CDATA[<p><img src="{SITE}{e["lead"]}" alt="{html.escape(e["alt"])}"></p>\n'
                f"{e['html']}]]></content:encoded>\n  </item>\n")
    built = format_datetime(dt.datetime.combine(essays[0]["date"], dt.time(9), SEOUL))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n<channel>\n'
            f"  <title>{AUTHOR} — Writing</title>\n  <link>{SITE}/writing/</link>\n"
            f'  <atom:link href="{SITE}/writing/feed.xml" rel="self" type="application/rss+xml"/>\n'
            f"  <description>Essays by {AUTHOR}.</description>\n  <language>en</language>\n"
            f"  <lastBuildDate>{built}</lastBuildDate>\n{''.join(item(e) for e in essays)}</channel>\n</rss>\n")


def main():
    essays = sorted((load(p) for p in (WRITING / "src").glob("*.md")), key=lambda e: e["date"], reverse=True)
    for e in essays:
        render_essay(e)
    latest = essays[0]
    index = fill("page.html", page_title=f"Writing — {AUTHOR}", description=f"Essays by {AUTHOR}.",
                 url=f"{SITE}/writing/", og_type="website", og_image=f"{SITE}{latest['media']}/og.jpg",
                 og_alt=html.escape(latest["alt"]), jsonld="",
                 content=fill("index.html", items="\n".join(card(e) for e in essays)))
    (WRITING / "index.html").write_text(index, encoding="utf-8")
    (WRITING / "feed.xml").write_text(feed(essays), encoding="utf-8")
    home = ROOT / "index.html"
    marked = re.compile(r"(<!-- writing:list -->).*?(\n\s*<!-- /writing:list -->)", re.S)
    rows = "\n".join(row(e) for e in essays[:3])
    home.write_text(marked.sub(lambda m: m.group(1) + "\n" + rows + m.group(2), home.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
