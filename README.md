# HAPLoD — code and data reproducibility

**Target journal:** Earth System Science Data (ESSD)  
**Dataset snapshot:** v1.1.0  
**Software correction in progress:** v1.1.2 (NOT yet a published or DOI-archived release)

HAPLoD is a provenance-aware database of polar-low tracks, event records and validation comparisons. The GitHub repository stores code and metadata, **not the entire dataset**. Obtain the separately archived HAPLoD v1.1 data package from the Zenodo dataset record; record 23495395 is a draft until published. The code release DOI 10.5281/zenodo.23494345 currently identifies the **earlier v1.1.1 version only**, not this correction.

## Dataset-snapshot checks

Unpack the approved dataset ZIP at the repository root, preserving `03_Data_Release/database/haplod_v1.1.sqlite` and `03_Data_Release/csv_complete/`.

```bash
python -m pip install -r 04_Code/requirements.txt
python 04_Code/validate_release.py
python 04_Code/test_sql_examples.py
python 04_Code/rebuild_release_sqlite.py --output reconstructed_haplod.sqlite
python 04_Code/test_roundtrip.py --rebuilt reconstructed_haplod.sqlite
```

The round-trip scripts reconstruct the 21-table published **database snapshot** from the released CSV tables. They do **not** independently reproduce the upstream data creation from source observations, and byte-identical SQLite output is not required. Numerical comparisons allow absolute floating-point differences no greater than 1e-10.

## Important distinctions

- **Level 1:** verify checksums, database integrity, published row counts, and SQL query execution.
- **Level 2:** reconstruct the complete tabular database snapshot from released CSV files plus the archived schema and compare rows.
- **Level 3:** independently rerun selected original track, IMPMCT and Rojo processing stages using their **10 original source files**; this requires a separately executed and documented test with the supplied original inputs.
- **Level 4:** full scientific reconstruction of all source catalogues from environmental observations, including the Farjami–Kazemi original detection pipeline, is **not established** by this repository.

See `04_Code/README_CODE.md` for limitations, `03_Data_Release/licenses/THIRD_PARTY_DATA_AND_LICENSES.md` for source-specific terms, and `CODE_LICENSE_DECISION_REQUIRED.md` for pending software-licence confirmation.

## Publication and citation

The dataset and software have **distinct records and identifiers**. A new **GitHub Release** at tag v1.1.2 is required before claiming a Zenodo software-version DOI for these corrections. Do not reuse the v1.1.1 version DOI for v1.1.2. Only after independently verifying Zenodo archival, update `CITATION.cff`, the manuscript Code availability section, the dataset metadata, and checksum manifests with the **actual new DOI**.

**Release gate:** a technical PASS is not a legal or scientific sign-off. Do not publish or replace a Zenodo data record until exact upstream redistribution rights, a verified anonymous reviewer-access URL, and author sign-off have been established. Do not commit Zenodo draft preview secrets, personal access tokens, or webhook URLs to GitHub.
