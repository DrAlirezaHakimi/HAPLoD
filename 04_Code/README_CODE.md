# Reproducibility and validation — HAPLoD v1.1.2

The dataset is maintained and distributed **separately from GitHub**. Obtain the HAPLoD v1.1.0 complete data archive (including 21 compressed CSV tables, database schema and SQLite database).

After unpacking it so that `03_Data_Release` lies at the repository root:

```sh
python 04_Code/validate_release.py
python 04_Code/test_sql_examples.py
python 04_Code/rebuild_release_sqlite.py --output reconstructed_haplod.sqlite
python 04_Code/test_roundtrip.py --rebuilt reconstructed_haplod.sqlite
```

The commands check the **database snapshot and round-trip** from released CSV tables. The round-trip compares table rows and accepts absolute numeric differences no greater than 1e-10. The CSV/SQLite round-trip does not establish raw-source reprocessing, detection reproducibility, or byte-identical SQLite databases. The supplied raw-source processing requires the original source files and a separate documented test; full re-detection of event records from environmental inputs is not claimed.

The original HAPLoD code is MIT-licensed (see root LICENSE). The source datasets are *not* automatically covered by that licence. Review the source attribution and reuse terms before distributing or using upstream inputs.

Version-specific software DOI must be verified from a Zenodo release; never cite a previous software version DOI as if it were v1.1.2.
