-- Reset leaderboard after removing old question-bank items.
-- Hide all attempts already created, including unfinished old-paper attempts,
-- so no mismatched papers can re-enter the new leaderboard.
-- Keep historical attempts and certificate records intact.
UPDATE attempts
SET defeated_at = CAST(strftime('%s','now') AS INTEGER) * 1000
WHERE defeated_at IS NULL;
