-- HAPLoD v1.1: six statements verified against the actual archived schema.
-- These query the documented 21-table snapshot, not absent views.

-- 1. Track summary
SELECT canonical_track_id, hemisphere, n_points
FROM track_summary ORDER BY canonical_track_id LIMIT 10;

-- 2. Track-resolved positions
SELECT canonical_track_id, time, lon, lat
FROM track_points ORDER BY canonical_track_id, time LIMIT 10;

-- 3. Source multiplicity
SELECT source_count, COUNT(*) AS n_tracks
FROM track_summary GROUP BY source_count ORDER BY source_count;

-- 4. Source-specific retention criteria
SELECT source, subset, n_tracks, all_criteria_pass_pct
FROM criteria_validation ORDER BY source, subset;

-- 5. Dataset quality-control results
SELECT area, metric, value, status
FROM qa_results ORDER BY area, metric;

-- 6. Southern Ocean event layer (day-precision timestamps only)
SELECT event_id, event_date, lat, lon, vort850_cyclonic_1e5_s1
FROM event_catalogue WHERE source = 'Farjami_Kazemi_2024'
ORDER BY event_date, event_id LIMIT 20;
