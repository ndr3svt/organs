# data_for_the_arts_showcase

A small standalone page that shows how the Organs dataset is made: five realms, a slider through the cutouts, a slider from source photograph to cutout to class mask, and a few honest numbers. Plain HTML, CSS and ES modules. No framework, no libraries, no third-party requests, no build step for the page itself.

It is built here and previewed locally, then copied into the portfolio's `static/organs/` to live at `ndr3svt.art/organs/`.

## Build and preview

From the `organs` folder:

```bash
.venv/bin/organs showcase                  # select, render thumbnails, write data/showcase.json, stamp cache versions
.venv/bin/organs showcase --serve          # the same, then preview at http://127.0.0.1:4180/
.venv/bin/organs showcase --skip-build     # preview only
.venv/bin/organs showcase --per-class 120  # more specimens per realm
```

The preview server maps `/fonts/`, `/avatar.gif` and `/favicon.png` read-only to `../avt_web_portfolio`, so the page looks as it will live. If that folder is absent the page falls back to a system sans.

## What is committed and what is not

- Committed: `index.html`, `css/`, `js/`, `data/showcase.json` (credits and aggregates), `curation.json`.
- Not committed: `img/`. The thumbnails are other people's photographs. They are generated locally and only committed in the private portfolio repository when the page is deployed.
- Not in this repository at all: the Aeonik Soft font. It is licensed. The page names it as `/fonts/AeonikSoft-Regular.otf`, which exists on the live site.

## Licenses

Only CC0, public domain, CC BY and CC BY-SA images are shown. Non-commercial images stay in the dataset but are never shown, because the portfolio also offers services. Every shown image carries author, license and source link in the page and in the Credits list. The cutouts are adaptations (background removed, cropped, resized), and the page says so. The exact license version is on each source page.

## Choosing what is shown

The sample is balanced per realm, kept images first, then spread across the search queries so it shows variety. Most images have not been reviewed by a person, so check the contact sheets after a build:

```
img/_contact_animal.jpg   img/_contact_plant.jpg   img/_contact_fungal.jpg
img/_contact_metaphor.jpg   img/_contact_scifi.jpg
```

Each tile is labeled with its id (`c_` is `commons_`, `i_` is `inat_`). Put ids you want gone in `curation.json` under `exclude`, ids you want forced in under `include`, whole sources under `exclude_sources`, and build again. Replacements are filled from the rest of the pool. Images you keep in the review tool (`organs review`) are picked first.

## Deploy

The portfolio copies `static/<name>/` as-is to `/<name>/` and lists it in the sitemap. From the `organs` folder, after a build:

```bash
rsync -a --exclude README.md --exclude curation.json --exclude 'img/_contact_*' data_for_the_arts_showcase/ ../avt_web_portfolio/static/organs/
cd ../avt_web_portfolio && npm run build
```

Then commit `static/organs` and `site/organs` in the portfolio repository and update the VPS as that repository's README describes (`git pull`, `npm run build`, `pm2 restart ndr3svt-portfolio`). Add a link to `/organs/` in `content/projects/18-organs/index.md` if wanted. The page uses relative asset paths, so it works at `/` and at `/organs/`.

The images are stored twice in the portfolio repository (`static/` and the tracked `site/`), about 24 MB in all.
