# HAPLoD v1.1 data release

HAPLoD v1.1 is a provenance-aware, multi-granularity reference database for polar-low research.

## Core contents
- **Track-resolved layer:** 18,981 canonical ERA5-matched time steps representing 632 tracks from six literature catalogues.
- **Common track subset:** 346 tracks satisfying the four Stoll (2022) lifetime criteria.
- **Event-resolved layer:** 1,073 Southern Ocean polar-low event snapshots from Farjami & Kazemi (2024), 2000-2020, with day-level time precision.
- **Validation layers:** 16,001 IMPMCT cloud features and 3,850 original Rojo satellite observations.

The track and event layers are intentionally separate. Do not concatenate them into a single frequency climatology without an explicit sampling model.

## Primary files
- `database/haplod_v1.1.sqlite`
- `csv/*.csv.gz`
- `metadata/data_dictionary.csv`
- `metadata/release_summary.json`
- `SHA256SUMS.txt`

## Citation
Use the repository DOI assigned to HAPLoD v1.1 and cite the upstream catalogues relevant to your analysis.
