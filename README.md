# French dissertations: supervision and co-authorship network

Builds supervision networks from the theses.fr dump (2005 onwards), links supervisors to ORCID, combines ORCID co-authorship with co-supervision, lays out and clusters the network (Leiden), and renders it in Blender (UniversityExplorer pipeline).

Data, Blender files, renders and bundled tools are not in the repo (see `.gitignore`).

## Setup
- Thesis data: `python3 scripts/load_theses_data.py` downloads the theses.fr dump from data.gouv.fr into `data/` (looks up the current file via the API; skips files already present).
- BigQuery: the SQL in `sql/` uses `{{BQ_PROJECT}}`, `{{BQ_DATASET}}` and `{{ORCID_TABLE}}` placeholders. Set `BQ_PROJECT` and `BQ_DATASET` (a dataset you can write to), then run e.g. `python3 scripts/run_bq.py sql/fr_coauthor_edges.sql --out output_2005/fr_coauthor_edges_orcid.csv`. Add `--dry-run` to see the rendered SQL. The queries read your own tables `fr_director_ids` (upload `output_2005/fr_director_ids.csv`), `fr_director_orcid_candidates` and `orcid_doi_2026` (the outputs of the other two queries, saved as tables in your dataset). `ORCID_TABLE` defaults to `ds-open-datasets.orcid.summaries_2026`.

## Pipeline (scripts/)
0. `load_theses_data.py`, `run_bq.py`: data download and BigQuery queries
1. `build_supervision_graph.py`, `build_advisor_network.py`: supervision edges from theses.fr
2. `link_ppn_identifiers.py`, `combine_coauthor_supervision.py`: ORCID linkage and the combined network
3. `layout_*.py` (BatchLayout), `communities_*.py` (Leiden)
4. `discipline_fields.py`: maps thesis discipline strings to 19 fields
5. `prepare_blender_inputs.py`, `geonodes_directors.py`: build the Blender scene
6. `render_stills.py`, `render_clip.py`, `render_segments.py`, `join_segments.py`: render and join (needs ffmpeg)

Paths are relative to the repo. Override with env vars: `FR_ROOT` (repo root), `BATCHLAYOUT_DIR` (BatchLayoutCode folder, default `~/batchlayout/BatchLayout/BatchLayoutCode`), `UE_PIPELINE` (UniversityExplorer graph-pipeline folder), `FFMPEG`, `BLENDER`.

## Blender
The build starts from `blender/templates/University_template_fr.blend` (committed). `geonodes_directors.py` writes the scene (`University.blend`) and `holds.json` into `blender/<asset>/`; these are generated, not committed. Example:

    blender -b blender/templates/University_template_fr.blend --python scripts/geonodes_directors.py -- fr-sub $PWD/blender/

Fonts are not committed (SF Pro is Apple-licensed). Put `SF-Pro-Display-Light.ttf` and `Antonio-VariableFont_wght.ttf` in `blender/templates/fonts/`; the template looks for them there (`//fonts/`).
