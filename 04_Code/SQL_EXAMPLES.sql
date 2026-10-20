-- HAPLoD v1.1: verified queries for published SQLite schema
SELECT canonical_track_id, hemisphere, tmi_time, tmi_lat, tmi_lon
FROM track_summary WHERE passes_all_stoll_criteria = 1 ORDER BY hemisphere, canonical_track_id;

SELECT p.* FROM track_points AS p
JOIN track_summary AS s ON p.canonical_track_id = s.canonical_track_id
WHERE s.passes_all_stoll_criteria = 1
ORDER BY p.canonical_track_id, p.time;

SELECT sources, COUNT(*) AS n_tracks FROM track_summary GROUP BY sources ORDER BY n_tracks DESC;

SELECT source, subset, n_tracks, all_criteria_pass_pct FROM criteria_validation ORDER BY source, subset;

SELECT event_id, event_date, lat, lon FROM event_catalogue
WHERE source = 'Farjami_Kazemi_2024' ORDER BY event_date;

PRAGMA integrity_check;
