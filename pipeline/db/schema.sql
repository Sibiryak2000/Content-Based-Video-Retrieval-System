CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    fps REAL NOT NULL,
    frame_count INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    proxy_path TEXT,
    vimeo_description TEXT
);

CREATE TABLE IF NOT EXISTS shots (
    shot_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    shot_index INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    keyframe_path TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE INDEX IF NOT EXISTS idx_shots_video_id ON shots(video_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    git_commit TEXT,
    config_hash TEXT,
    notes TEXT
);
