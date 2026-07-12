"""SQLite persistence for pipeline metadata."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pipeline.db.models import ShotRecord, ShotWithVideo, VideoRecord

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _rel_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


class MetadataStore:
    def __init__(self, db_path: Path, repo_root: Path):
        self.db_path = db_path
        self.repo_root = repo_root
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(sql)

    def upsert_video(self, record: VideoRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO videos (video_id, filename, fps, frame_count, width, height, proxy_path, vimeo_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    filename=excluded.filename,
                    fps=excluded.fps,
                    frame_count=excluded.frame_count,
                    width=excluded.width,
                    height=excluded.height,
                    proxy_path=excluded.proxy_path,
                    vimeo_description=excluded.vimeo_description
                """,
                (
                    record.video_id,
                    record.filename,
                    record.fps,
                    record.frame_count,
                    record.width,
                    record.height,
                    record.proxy_path,
                    record.vimeo_description,
                ),
            )

    def upsert_shot(self, record: ShotRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO shots (shot_id, video_id, shot_index, start_frame, end_frame, keyframe_path)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(shot_id) DO UPDATE SET
                    video_id=excluded.video_id,
                    shot_index=excluded.shot_index,
                    start_frame=excluded.start_frame,
                    end_frame=excluded.end_frame,
                    keyframe_path=excluded.keyframe_path
                """,
                (
                    record.shot_id,
                    record.video_id,
                    record.shot_index,
                    record.start_frame,
                    record.end_frame,
                    record.keyframe_path,
                ),
            )

    def _row_to_shot(self, r: sqlite3.Row) -> ShotWithVideo:
        return ShotWithVideo(
            shot_id=r["shot_id"],
            video_id=r["video_id"],
            shot_index=r["shot_index"],
            start_frame=r["start_frame"],
            end_frame=r["end_frame"],
            keyframe_path=r["keyframe_path"],
            fps=r["fps"],
            proxy_path=r["proxy_path"],
        )

    def _shots_query(self, where: str = "", params: tuple = ()) -> str:
        return f"""
            SELECT s.shot_id, s.video_id, s.shot_index, s.start_frame, s.end_frame,
                   s.keyframe_path, v.fps, v.proxy_path, v.vimeo_description
            FROM shots s
            JOIN videos v ON s.video_id = v.video_id
            {where}
            ORDER BY s.video_id, s.shot_index
        """

    def list_shots(
        self,
        limit: int,
        offset: int,
        video_id: str | None = None,
        query: str = "",
    ) -> List[ShotWithVideo]:
        clauses: List[str] = []
        params: List[object] = []
        if video_id:
            clauses.append("s.video_id = ?")
            params.append(video_id)
        if query.strip():
            q = query.strip()
            clauses.append("(s.video_id LIKE ? OR v.vimeo_description LIKE ?)")
            params.extend([f"{q}%", f"%{q}%"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = self._shots_query(where) + " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_shot(r) for r in rows]

    def count_shots(self, video_id: str | None = None, query: str = "") -> int:
        clauses: List[str] = []
        params: List[object] = []
        if video_id:
            clauses.append("s.video_id = ?")
            params.append(video_id)
        if query.strip():
            q = query.strip()
            clauses.append("(s.video_id LIKE ? OR v.vimeo_description LIKE ?)")
            params.extend([f"{q}%", f"%{q}%"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT COUNT(*) AS cnt
            FROM shots s
            JOIN videos v ON s.video_id = v.video_id
            {where}
        """
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["cnt"]) if row else 0

    def search_shots_by_video_id_prefix(self, prefix: str, limit: int) -> List[ShotWithVideo]:
        return self.list_shots(limit=limit, offset=0, query=prefix)

    @staticmethod
    def resolve_path(path_str: str | None, repo_root: Path) -> str | None:
        if not path_str:
            return None
        p = Path(path_str)
        if p.is_absolute():
            return str(p.resolve())
        return str((repo_root / p).resolve())

    def to_result_item(self, shot: ShotWithVideo, title: str | None = None) -> dict:
        return {
            "video_id": shot.video_id,
            "shot_id": shot.shot_id,
            "title": title or shot.video_id,
            "keyframe_path": self.resolve_path(shot.keyframe_path, self.repo_root),
            "proxy_path": self.resolve_path(shot.proxy_path, self.repo_root),
            "start_frame": shot.start_frame,
            "end_frame": shot.end_frame,
            "fps": shot.fps,
            "score": 0.0,
            "text": None,
        }

    def count_videos(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM videos").fetchone()
        return int(row["cnt"]) if row else 0

    def list_shots_for_video(self, video_id: str) -> List[ShotWithVideo]:
        with self.connect() as conn:
            rows = conn.execute(
                self._shots_query("WHERE s.video_id = ?"),
                (video_id,),
            ).fetchall()
        return [self._row_to_shot(r) for r in rows]

    def log_run(self, config_path: Path, notes: str = "") -> int:
        config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()[:16]
        git_commit: Optional[str] = None
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        ts = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO pipeline_runs (timestamp, git_commit, config_hash, notes)
                VALUES (?, ?, ?, ?)
                """,
                (ts, git_commit, config_hash, notes),
            )
            return int(cur.lastrowid)

    def export_sample_result_items(self, video_id: str, limit: int = 3) -> List[dict]:
        """Export ResultItem-compatible dicts for GUI handoff."""
        shots = self.list_shots_for_video(video_id)[:limit]
        return [self.to_result_item(s) for s in shots]

    @staticmethod
    def make_relative(path: Path, repo_root: Path) -> str:
        return _rel_path(path, repo_root)
