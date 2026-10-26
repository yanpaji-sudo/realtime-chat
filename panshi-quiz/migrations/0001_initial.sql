CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY,
  token TEXT NOT NULL,
  nickname TEXT NOT NULL,
  started_at INTEGER NOT NULL,
  question_plan TEXT NOT NULL,
  finished_at INTEGER,
  score INTEGER,
  correct_count INTEGER,
  elapsed_seconds INTEGER
);
CREATE INDEX IF NOT EXISTS idx_attempts_active ON attempts(finished_at,started_at);
CREATE INDEX IF NOT EXISTS idx_attempts_leaderboard ON attempts(finished_at,score DESC,elapsed_seconds ASC);