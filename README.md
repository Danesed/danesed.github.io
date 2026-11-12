# danesed.github.io

The source of my academic page, [danesed.github.io](https://danesed.github.io).

One page: who I am, my publications, my CV. No framework and nothing to install.

## How it works

- `site/` is the page: `index.html`, and `assets/` with the portrait, the main figure
  of each paper and the curves of the animation.
- `build.py` reads my publications from [dblp](https://dblp.org/pid/372/0698), writes
  them into the page with their links and BibTeX, and puts the result in `_site/`.
- `.github/workflows/deploy.yml` runs the build on every push and once a day, then
  publishes `_site/` to GitHub Pages. A paper appears on the page the day after dblp
  indexes it.

```sh
python3 build.py             # read dblp, build into _site/
python3 build.py --offline   # build from data/publications.json
python3 -m http.server -d _site 8000
```

## What to edit

| To change | Edit |
| --- | --- |
| Text, CV, links, colours | `site/index.html` |
| A code or project link on a paper | `data/extra.json`, under `links`, by dblp key |
| A paper dblp does not list yet | `data/extra.json`, under `publications` |
| A paper's picture | `site/assets/papers/<dblp key with _ for />.jpg`, its main figure |
| Two dblp records that are one paper | `data/extra.json`, under `same`, the keys together |

A manual paper looks like this, and is dropped by itself once dblp lists the same title:

```json
{
  "title": "A Paper dblp Has Not Indexed Yet",
  "authors": ["Danilo Danese", "A. Coauthor"],
  "venue": "MICCAI",
  "year": 2026,
  "kind": "conference",
  "links": { "Paper": "https://…", "Code": "https://github.com/…" },
  "bibtex": "@inproceedings{…}"
}
```

`data/publications.json` is the last answer from dblp. It is committed so the site
builds when dblp cannot be reached; `build.py` rewrites it when the list changes.

## Publications and dblp

The records come from dblp's SPARQL service, the interface dblp offers to programs.
The BibTeX is written from those records in dblp's own layout, with dblp's keys. A
paper with a preprint and a published version is listed once, as the published
version, with the preprint as its arXiv link.

## The curves

The bands on the cover are cortical folds: the grey/white boundary at four depths,
traced from neighbouring sagittal slices of my brain MRI. The page moves slowly from
one slice to the next. They are the motif of my thesis cover.
