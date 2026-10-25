-- HAPLoD v1.1 examples against actual data tables (no fabricated views).
-- 1: standardized track list
SELECT * FROM standardized_polar_low_tracks ORDER BY hemisphere, start_time;
-- 2: standardized track points
SELECT * FROM standardized_polar_low_points ORDER BY canonical_track_id, time;
-- 3: overlap
SELECT source_count, COUNT(*) AS tracks FROM track_summary GROUP BY source_count ORDER BY source_count;
-- 4: retention criteria
SELECT source, subset, n_tracks, all_criteria_pass_pct FROM criteria_validation ORDER BY source, subset;
-- 5: warnings
SELECT * FROM qa_warnings;
-- 6: Farjami-Kazemi event-level records
SELECT event_id, event_date, lat, lon, vort850_cyclonic_1e5_s1
FROM event_catalogue WHERE source = 'Farjami_Kazemi_2024'
ORDER BY event_date, event_id;
