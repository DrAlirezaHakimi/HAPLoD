# Known limitations

1. HAPLoD harmonizes heterogeneous source catalogues; it is not a uniform detection climatology.
2. Northern and Southern source coverage differs in region, period, sensor/protocol, and temporal granularity.
3. Farjami & Kazemi (2024) records are day-precision event snapshots and are not reconstructed as hourly life-cycle tracks.
4. Common Stoll (2022) criteria are lifetime aggregation operators and are applied only to the track-resolved layer.
5. Potential Farjami-Kazemi/Verezemskaya cross-links are supplied as candidates and are not automatically merged.
6. ERA5-matched track centres represent reanalysis vortices and need not coincide exactly with satellite cloud-feature centres.
7. Fast IMPMCT translation intervals are flagged rather than silently deleted.
