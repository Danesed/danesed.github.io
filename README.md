# danesed.github.io

Source for my personal academic site, [danesed.github.io](https://danesed.github.io).

I'm Danilo Danese, a PhD student at [SisInfLab](https://sisinflab.poliba.it/), Polytechnic University of Bari, working on generative models in high-dimensional low-sample-size (HDLSS) domains.

## Stack

- [Astro](https://astro.build) — static site generator
- [Tailwind CSS](https://tailwindcss.com/) + [DaisyUI](https://daisyui.com/)
- Deployed to GitHub Pages via [`.github/workflows/`](.github/workflows/)

## Local development

```bash
pnpm install
pnpm dev      # http://localhost:4321
pnpm build    # static output in ./dist
```

## Content

- **Pages** live in [`src/pages/`](src/pages/)
- **Blog posts** are markdown in [`src/content/blog/`](src/content/blog/) (schema in [`src/content/config.ts`](src/content/config.ts))
- **Static assets** (images, favicon, robots, social card) live in [`public/`](public/)

## Credit

Originally forked from the [astrofy](https://github.com/manuelernestog/astrofy) template by Manuel Ernesto Garcia (MIT).
