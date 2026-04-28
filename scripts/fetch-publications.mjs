#!/usr/bin/env node
// Fetches Danilo's publications from Semantic Scholar and writes them to
// src/data/publications.json. The committed JSON acts as a fallback so the
// build never breaks if the API is rate-limiting or down.
//
// Run automatically before `astro build` (see "prebuild" in package.json).
// Run manually with: pnpm fetch:publications

import { writeFile, readFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AUTHOR_ID = "2290185261"; // Danilo Danese on Semantic Scholar
const FIELDS = [
    "title",
    "year",
    "venue",
    "publicationVenue",
    "publicationDate",
    "externalIds",
    "openAccessPdf",
    "abstract",
    "authors.authorId",
    "authors.name",
].join(",");

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_PATH = resolve(__dirname, "../src/data/publications.json");

const apiKey = process.env.SEMANTIC_SCHOLAR_API_KEY;
const headers = apiKey ? { "x-api-key": apiKey } : {};

async function fetchPapers() {
    const url = `https://api.semanticscholar.org/graph/v1/author/${AUTHOR_ID}/papers?fields=${FIELDS}&limit=100`;
    const res = await fetch(url, { headers });
    if (!res.ok) {
        throw new Error(`Semantic Scholar returned ${res.status}: ${await res.text()}`);
    }
    const json = await res.json();
    return json.data ?? [];
}

function pickLink(p) {
    const ids = p.externalIds ?? {};
    if (ids.ArXiv) return `https://arxiv.org/abs/${ids.ArXiv}`;
    if (p.openAccessPdf?.url) return p.openAccessPdf.url;
    if (ids.DOI) return `https://doi.org/${ids.DOI}`;
    return `https://www.semanticscholar.org/paper/${p.paperId}`;
}

function pickVenue(p) {
    const name = p.publicationVenue?.name ?? p.venue ?? "";
    // Prefer the conference acronym when it's present in alternate_names
    // (e.g. "International Conference on Information and Knowledge Management" → "CIKM").
    const alternates = p.publicationVenue?.alternate_names ?? [];
    const acronym = alternates.find((a) => /^[A-Z]{2,8}$/.test(a));
    return acronym ?? name;
}

function transform(papers) {
    return papers
        .map((p) => ({
            id: p.paperId,
            title: p.title,
            year: p.year,
            date: p.publicationDate ?? null,
            venue: pickVenue(p),
            authors: (p.authors ?? []).map((a) => a.name),
            link: pickLink(p),
            abstract: p.abstract ?? null,
        }))
        .sort((a, b) => {
            // Newest first. Use date if both have one, otherwise year.
            if (a.date && b.date) return b.date.localeCompare(a.date);
            return (b.year ?? 0) - (a.year ?? 0);
        });
}

async function readCache() {
    try {
        return JSON.parse(await readFile(OUT_PATH, "utf8"));
    } catch {
        return null;
    }
}

async function main() {
    let publications;
    try {
        const papers = await fetchPapers();
        publications = transform(papers);
        console.log(`✓ Fetched ${publications.length} publications from Semantic Scholar`);
    } catch (err) {
        const cached = await readCache();
        if (cached) {
            console.warn(`⚠ Semantic Scholar fetch failed (${err.message}). Using cached publications.json.`);
            return;
        }
        console.error(`✗ Semantic Scholar fetch failed and no cache exists: ${err.message}`);
        process.exit(1);
    }
    await mkdir(dirname(OUT_PATH), { recursive: true });
    await writeFile(OUT_PATH, JSON.stringify(publications, null, 2) + "\n", "utf8");
}

main();
