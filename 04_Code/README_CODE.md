# HAPLoD v1.1.2 software verification guide

The full dataset is deposited separately. To perform the documented checks, unpack its `03_Data_Release` directory at the repository root.

1. Run `python 04_Code/validate_release.py` to check integrity and essential counts.
2. Run `python 04_Code/test_sql_examples.py` to execute every SQL query in `04_Code/SQL_EXAMPLES.sql`.
3. Run `python 04_Code/rebuild_release_sqlite.py --output reconstructed_haplod.sqlite` to rebuild the **released table snapshot** from all 21 CSV exports and the released schema.
4. Run `python 04_Code/test_roundtrip.py --rebuilt reconstructed_haplod.sqlite` to compare table contents, tolerating numeric error <= 1e-10.

These steps do not reconstruct all upstream polar-low detections from ERA5 or observational raw input. The original raw-catalogue processing requires separate input files and independent evidence. The Farjami–Kazemi event catalogue must not be described as fully regenerated from source environmental measurements by these checks.

Before archiving edited software, verify the software licence, source attribution, and version-specific DOI. Do not add private Zenodo draft URLs or tokens to this public repository.
