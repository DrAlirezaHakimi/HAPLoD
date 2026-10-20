# HAPLoD v1.1 — source code and documentation

A provenance-aware, multi-granularity reference database of polar-low tracks and Southern Ocean event snapshots.

**Article target:** Earth System Science Data (ESSD). **Software version:** v1.1.0.

## Repository contents

- `04_Code/build_track_resolved_core.py` — builds upstream track-resolved core from original inputs.
- `04_Code/integrate_farjami_kazemi.py` — adds harmonized event snapshots to a pre-existing compatible SQLite DB.
- `04_Code/generate_figures.py` — regenerates figures from the dataset release files.
- `04_Code/validate_release.py` — asserts database counts, integrity, and some known properties.
- `04_Code/SQL_EXAMPLES.sql` — example queries for the final schema.
- `03_Data_Release/metadata` — schema and release information (NOT the full database).

**The dataset is deliberately NOT stored in Git.** Download the dataset record from Zenodo and unpack its `03_Data_Release` directory into the root of the checked-out repository; then run:

```bash
python -m pip install -r 04_Code/requirements.txt
python 04_Code/validate_release.py
python 04_Code/generate_figures.py
```

The scripts have additional input/output assumptions and must be independently tested against the original upstream inputs before asserting end-to-end reconstruction from raw data. In particular, do not treat `integrate_farjami_kazemi.py` as a standalone implementation of every table in the already integrated database.

## Citation and licensing

Cite the original Stoll, IMPMCT, Rojo, and Farjami–Kazemi data sources separately, as well as the eventual HAPLoD dataset DOI. Do not assign a blanket licence to third-party data without verifying source licences. The code licence is awaiting confirmation by all code owners.

## Data publication

- GitHub Release `v1.1.0` → software archive in Zenodo and **software DOI**.
- Separate Zenodo `Dataset` record → full validated SQLite, CSV, metadata, checksums, and **data DOI**.
- Both must correspond to the same v1.1.0 source snapshot. The Data DOI, not the software DOI, is the primary identifier in the ESSD Data availability section.
