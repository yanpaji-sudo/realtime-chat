-- PK challenges: keep original quiz plans; preserve challenged history.
ALTER TABLE attempts ADD COLUMN is_pk INTEGER NOT NULL DEFAULT 0;
ALTER TABLE attempts ADD COLUMN challenge_target_id TEXT;
ALTER TABLE attempts ADD COLUMN challenge_target_nickname TEXT;
ALTER TABLE attempts ADD COLUMN challenge_target_score INTEGER;
ALTER TABLE attempts ADD COLUMN pk_success INTEGER NOT NULL DEFAULT 0;
ALTER TABLE attempts ADD COLUMN defeated_at INTEGER;
CREATE TABLE IF NOT EXISTS pk_challenges (
  id TEXT PRIMARY KEY,
  target_id TEXT NOT NULL,
  target_nickname TEXT NOT NULL,
  challenger_nickname TEXT NOT NULL,
  success INTEGER NOT NULL DEFAULT 0,
  finished_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pk_challenges_target ON pk_challenges(target_nickname);
CREATE INDEX IF NOT EXISTS idx_attempts_pk_ranking ON attempts(defeated_at,finished_at,score DESC);
