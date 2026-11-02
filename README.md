# organs

Draw a silhouette in a class color, get a specimen image back. A small GAN for mask-to-image synthesis (SPADE / OASIS family), not diffusion. A follow-up to the earlier pix2pix experiment at <https://ndr3svt.art/projects/organs/>.

Organs here means organs in a wide sense: animal organs, plant organs (leaf, fruit, flower, root), fungal bodies, and metaphorical organs (bellows, pumps, circuit boards). The model sees a class-index map with four classes plus background, and has to commit to a single plausible specimen instead of the pixel average that pix2pix produces.

## Status

| Stage | State |
|---|---|
| Collect open-license images | working (Commons, iNaturalist, Wellcome) |
| Cutout onto a neutral ground, class-index masks | working |
| Keep / reject review | working |
| Local proof-of-concept training (128px, Mac) | not started |
| Cloud training (256px) and the drawing tool | not started |

Openverse is not used: its API did not respond when this was built.

## Data policy

Images are never committed. `data/` is gitignored and holds the private dataset with a manifest recording the source URL, license, author, and class of every file. Only CC0, public domain, and CC BY family licenses without NoDerivatives are accepted. Trained weights are not published until the manifest licenses are audited, because share-alike and non-commercial terms can carry over to them.

## Classes

| index | class | swatch |
|---|---|---|
| 0 | background | none |
| 1 | animal | red |
| 2 | plant | green |
| 3 | fungal | amber |
| 4 | metaphor | blue |

## Setup

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e '.[cutout]'     # add '.[train]' when training
cp .env.example .env                      # keys stay local, .env is gitignored
```

## Workflow

```bash
organs collect --limit 40          # new images per query in queries.yaml; --source, --cls to narrow
organs ingest-inbox                # register your own images from data/inbox/<class>/
organs cutout                      # background removal, masks, automatic checks
organs review                      # keep / reject in the browser (K / R); --status auto_reject to rescue
organs stats                       # counts per class and status
```

Each image moves through the manifest statuses `raw`, then `cut` or `auto_reject`, then `keep` or `reject`. Only `keep` is used for training.

Every cutout is placed on one flat ground color, so the model learns the organ and not the photographed background.

## Method

The target network is a SPADE generator on the one-hot class map with spatial noise, trained against an OASIS-style per-pixel discriminator on a frozen pretrained backbone (the DP-SIMS idea, CVPR 2024), with DiffAugment for the small dataset. One forward pass produces one sample; the mean of several samples gives the blurred average.

Training is planned in two steps: a 128px proof of concept on Apple Silicon once the collection is annotated, then a 256px run on a rented GPU. The checkpoint comes back to the Mac for local inference.
