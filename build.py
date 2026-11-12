#!/usr/bin/env python3
"""Builds the site into _site/.

    python3 build.py            fetch the publications from dblp, then build
    python3 build.py --offline  build from data/publications.json as it is

The page is site/index.html with the publication list written into it. Everything
else in site/ is copied as it is. Standard library only, so there is nothing to install and nothing
to keep up to date.

Publications come from dblp's SPARQL service, the interface dblp offers to programs.
The result is also written to data/publications.json, which is committed: when dblp
cannot be reached, the build uses that copy and the site still deploys.

data/extra.json adds what dblp does not know: links to code or a project page for a
record, two records that are one paper under two titles, and papers dblp has not
indexed yet.

A paper's picture is site/assets/papers/<dblp key with _ for />.jpg, its main
figure. A paper without one gets the page's wave on the blue field instead.
"""
from __future__ import annotations

import datetime
import html
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
OUT = ROOT / "_site"
CACHE = ROOT / "data" / "publications.json"
EXTRA = ROOT / "data" / "extra.json"

AUTHOR = "Danilo Danese"
PID = "372/0698"
ENDPOINT = "https://sparql.dblp.org/sparql"
SCHEMA = "https://dblp.org/rdf/schema#"

RECORDS = f"""
PREFIX dblp: <{SCHEMA}>
SELECT ?pub ?p ?o WHERE {{
  ?pub dblp:authoredBy <https://dblp.org/pid/{PID}> .
  ?pub ?p ?o .
}}"""

SIGNATURES = f"""
PREFIX dblp: <{SCHEMA}>
SELECT ?pub ?ord ?name WHERE {{
  ?pub dblp:authoredBy <https://dblp.org/pid/{PID}> ; dblp:hasSignature ?s .
  ?s dblp:signatureOrdinal ?ord ; dblp:signatureDblpName ?name .
}}"""

# How a kind of record is named on the page, and the order two versions of one
# paper are preferred in: the journal article over the conference paper over the
# preprint over the dataset.
KINDS = {"journal": "Journal", "conference": "Conference", "preprint": "Preprint",
         "data": "Dataset", "other": "Publication"}
RANK = ["journal", "conference", "other", "preprint", "data"]


# ---------------------------------------------------------------- dblp

def sparql(query: str) -> list[dict]:
    request = urllib.request.Request(
        ENDPOINT,
        data=urllib.parse.urlencode({"query": query}).encode(),
        headers={"Accept": "application/sparql-results+json",
                 "User-Agent": "danesed.github.io build (personal academic page)"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)["results"]["bindings"]


def fetch() -> list[dict]:
    """Every dblp record of the author, as plain dictionaries."""
    fields: dict[str, dict[str, list[str]]] = {}
    for row in sparql(RECORDS):
        name = row["p"]["value"].rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        fields.setdefault(row["pub"]["value"], {}).setdefault(name, []).append(row["o"]["value"])
    authors: dict[str, list[tuple[int, str]]] = {}
    for row in sparql(SIGNATURES):
        authors.setdefault(row["pub"]["value"], []).append((int(row["ord"]["value"]), row["name"]["value"]))

    records = []
    for uri, f in fields.items():
        def one(name: str) -> str | None:
            return f.get(name, [None])[0]

        types = {t.rsplit("#", 1)[-1] for t in f.get("type", [])}
        kind = ("data" if "Data" in types else "preprint" if "Informal" in types
                else "journal" if "Article" in types else "conference" if "Inproceedings" in types
                else "other")
        doi = one("doi")
        records.append({
            "key": uri.replace("https://dblp.org/rec/", ""),
            "kind": kind,
            "title": (one("title") or "").rstrip(".").strip(),
            # dblp numbers homonyms ("Wei Wang 0001"); the number is not part of a name.
            "authors": [re.sub(r"\s+\d{4}$", "", name) for _, name in sorted(authors.get(uri, []))],
            "venue": one("publishedIn") or one("publishedBy") or "",
            "volume": one("publishedInJournalVolume"),
            "pages": one("pagination"),
            "year": int(one("yearOfEvent") or one("yearOfPublication") or 0) or None,
            "published": int(one("yearOfPublication") or 0) or None,
            "doi": doi.replace("https://doi.org/", "") if doi else None,
            "url": one("primaryDocumentPage") or doi,
        })
    return records


# ---------------------------------------------------------------- shaping

def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def arxiv_id(record: dict) -> str | None:
    match = re.search(r"arxiv\.(\d{4}\.\d{4,5})", (record.get("doi") or "").lower())
    return match.group(1) if match else None


def works(records: list[dict], extra: dict) -> list[dict]:
    """One entry per paper: its best version, with the others folded in as links."""
    # Records that are one paper although their titles differ, by dblp key.
    alias: dict[str, str] = {}
    for keys in extra.get("same", []):
        for key in keys:
            alias[key] = keys[0]

    all_records = list(records)
    for manual in extra.get("publications", []):
        m_slug = slug(manual.get("title", ""))
        # If dblp already has this paper at the same or better rank, dblp has done its job.
        if any(slug(r["title"]) == m_slug and RANK.index(r["kind"]) <= RANK.index(manual.get("kind", "other")) for r in records):
            continue
        all_records.append({
            "key": manual.get("key", ""),
            "kind": manual.get("kind", "other"),
            "venue": manual.get("venue", ""),
            "volume": manual.get("volume"),
            "pages": manual.get("pages"),
            "year": manual.get("year"),
            "published": manual.get("published") or manual.get("year"),
            "doi": manual.get("doi"),
            "url": manual.get("url"),
            "authors": manual.get("authors", []),
            "title": manual.get("title", ""),
            "manual": True,
            **manual,
        })

    groups: dict[str, list[dict]] = {}
    for record in all_records:
        groups.setdefault(alias.get(record["key"]) or slug(record["title"]), []).append(record)

    result = []
    for versions in groups.values():
        versions.sort(key=lambda r: (RANK.index(r["kind"]), 1 if r.get("manual") else 0, -(r["published"] or 0)))
        main = versions[0]
        links: list[tuple[str, str]] = []
        if main["kind"] == "preprint" and arxiv_id(main):
            links.append(("arXiv", f"https://arxiv.org/abs/{arxiv_id(main)}"))
        elif main.get("url"):
            if "arxiv.org" in (main.get("url") or ""):
                links.append(("arXiv", main["url"]))
            else:
                links.append(("Dataset" if main["kind"] == "data" else "Paper", main["url"]))
        for other in versions[1:]:
            if other["kind"] == "preprint" and arxiv_id(other):
                links.append(("arXiv", f"https://arxiv.org/abs/{arxiv_id(other)}"))
            elif other["kind"] == "data" and other.get("url"):
                links.append(("Dataset", other["url"]))
            elif other.get("url") and not any(l[1] == other["url"] for l in links):
                links.append(("Paper", other["url"]))
        for version in versions:
            links += list(extra.get("links", {}).get(version["key"], {}).items())
            if version.get("manual") and isinstance(version.get("links"), dict):
                links += list(version["links"].items())
            elif version.get("manual") and isinstance(version.get("links"), list):
                links += version["links"]
        if not main.get("manual"):
            links.append(("dblp", f"https://dblp.org/rec/{main['key']}"))
        else:
            dblp_ver = next((v for v in versions if not v.get("manual") and v.get("key")), None)
            if dblp_ver:
                links.append(("dblp", f"https://dblp.org/rec/{dblp_ver['key']}"))
        seen: set[str] = set()
        unique = [(label, url) for label, url in links if not (url in seen or seen.add(url))]
        # Two datasets or two preprints of one paper: keep the first of each label.
        labels: set[str] = set()
        unique = [(label, url) for label, url in unique if not (label in labels or labels.add(label))]
        result.append({**main, "links": unique, "bibtex": main.get("bibtex") or bibtex(main),
                       "figure": next((f for f in (figure(v["key"]) for v in versions) if f), None)})

    result.sort(key=lambda w: (-(w["year"] or 0), RANK.index(w["kind"]), w["title"]))
    return result


def figure(key: str) -> str | None:
    """The picture of a record, as a path inside the site, when there is one."""
    path = Path("assets") / "papers" / (key.replace("/", "_") + ".jpg")
    return path.as_posix() if key and (SITE / path).exists() else None


def bibtex(r: dict) -> str:
    """The record as dblp writes it in BibTeX: same key, same fields, same layout."""
    entry = {"journal": "article", "preprint": "article", "conference": "inproceedings",
             "data": "misc"}.get(r["kind"], "misc")
    fields: list[tuple[str, str]] = [
        ("author", " and\n                  ".join(r["authors"])),
        ("title", r["title"]),
    ]
    if r["kind"] == "conference":
        fields.append(("booktitle", r["venue"]))
    elif r["kind"] in ("journal", "preprint"):
        fields.append(("journal", r["venue"]))
        if r["volume"]:
            fields.append(("volume", r["volume"]))
    elif r["venue"]:
        fields.append(("publisher", r["venue"]))
    if r["pages"]:
        fields.append(("pages", r["pages"].replace("-", "--")))
    if r["published"]:
        fields.append(("year", str(r["published"])))
    if r["url"]:
        fields.append(("url", r["url"]))
    if r["doi"]:
        fields.append(("doi", r["doi"]))
    if arxiv_id(r):
        fields += [("eprinttype", "arXiv"), ("eprint", arxiv_id(r))]
    if not r.get("manual") and r.get("key"):
        fields += [("biburl", f"https://dblp.org/rec/{r['key']}.bib"),
                   ("bibsource", "dblp computer science bibliography, https://dblp.org")]
    body = ",\n".join(f"  {name:<12} = {{{value}}}" for name, value in fields)
    key_prefix = "" if r.get("manual") else "DBLP:"
    return f"@{entry}{{{key_prefix}{r['key']},\n{body}\n}}"


# ---------------------------------------------------------------- page

def esc(text: str) -> str:
    return html.escape(text, quote=True)


def venue_line(w: dict) -> str:
    parts = [w["venue"]] if w["venue"] else []
    if w["kind"] == "journal" and w["volume"]:
        parts[-1:] = [f"{w['venue']} {w['volume']}"]
    if w["year"]:
        parts.append(str(w["year"]))
    return " · ".join(parts)


def render(items: list[dict]) -> str:
    out: list[str] = []
    year = object()
    for w in items:
        if w["year"] != year:
            if out:
                out.append("</ol></section>")
            year = w["year"]
            out.append(f'<section class="year" aria-label="{year or "Undated"}">'
                       f'<h3 class="year-mark" data-reveal>{year or "Undated"}</h3><ol class="pubs">')
        authors = ", ".join(f"<b>{esc(a)}</b>" if a == AUTHOR else esc(a) for a in w["authors"])
        first = w["links"][0][1] if w["links"] else None
        title = f'<a href="{esc(first)}">{esc(w["title"])}</a>' if first else esc(w["title"])
        links = "".join(f'<a class="pill small" href="{esc(url)}">{esc(label)}</a>' for label, url in w["links"])
        bib = ""
        if w["bibtex"]:
            bib = ('<details class="bib"><summary class="pill small">BibTeX</summary>'
                   f'<div class="bib-box"><button class="pill small copy" type="button">Copy</button>'
                   f'<pre>{esc(w["bibtex"])}</pre></div></details>')
        if w.get("figure"):
            thumb = (f'<button class="thumb" type="button" data-figure="{esc(w["figure"])}" '
                     f'aria-label="Enlarge the main figure of {esc(w["title"])}">'
                     f'<img src="{esc(w["figure"])}" alt="" loading="lazy" decoding="async"></button>')
        else:
            thumb = '<span class="thumb none" aria-hidden="true"><i class="wave"></i></span>'
        out.append(
            f'<li class="pub" data-kind="{w["kind"]}" data-reveal>{thumb}'
            f'<div class="pub-body">'
            f'<p class="pub-venue"><span class="kind">{KINDS[w["kind"]]}</span>{esc(venue_line(w))}</p>'
            f'<h4 class="pub-title">{title}</h4>'
            f'<p class="pub-authors">{authors}</p>'
            f'<div class="pub-links">{links}{bib}</div>'
            f'</div></li>')
    if out:
        out.append("</ol></section>")
    return "\n".join(out)


def main() -> None:
    extra = json.loads(EXTRA.read_text()) if EXTRA.exists() else {}
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {"updated": None, "records": []}
    if "--offline" not in sys.argv:
        try:
            records = fetch()
            if not records:
                raise RuntimeError("dblp returned no records")
            records.sort(key=lambda r: r["key"])
            if records != cache["records"]:
                cache = {"updated": datetime.date.today().isoformat(), "records": records}
                CACHE.parent.mkdir(exist_ok=True)
                CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False) + "\n")
                print(f"dblp: {len(records)} records, cache updated")
            else:
                print(f"dblp: {len(records)} records, no change")
        except Exception as error:  # the site must still build from the cache
            print(f"dblp could not be read ({error}); using data/publications.json", file=sys.stderr)
    if not cache["records"]:
        sys.exit("no publications: dblp could not be read and there is no cache")

    items = works(cache["records"], extra)
    updated = datetime.date.fromisoformat(cache["updated"]) if cache["updated"] else datetime.date.today()
    page = (SITE / "index.html").read_text()
    if "<!--PUBLICATIONS-->" not in page:
        sys.exit("site/index.html has no <!--PUBLICATIONS--> placeholder")
    page = page.replace("<!--PUBLICATIONS-->", render(items))
    page = page.replace("<!--UPDATED-->", f"{updated.day} {updated:%B %Y}")

    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(SITE, OUT)
    (OUT / "index.html").write_text(page)
    (OUT / ".nojekyll").touch()
    print(f"built {len(items)} publications into {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
