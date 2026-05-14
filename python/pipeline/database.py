"""
SQLite metadata cache for the Asset Browser.
CACHE LAYER ONLY — metadata.json files on disk remain canonical.
Rebuild anytime: AssetDatabase().rebuild_from_index(project_folder)
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import _PIPELINE_ROOT
from .entities import load_projects
from .indexer import write_project_index, read_project_index

logger = logging.getLogger("pipeline")

DEFAULT_DB = _PIPELINE_ROOT / ".pipeline" / "asset_browser.db"

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS assets (
    uuid TEXT PRIMARY KEY,
    project TEXT NOT NULL DEFAULT '',
    entity TEXT NOT NULL DEFAULT '',
    task TEXT NOT NULL DEFAULT '',
    publish_type TEXT NOT NULL DEFAULT '',
    publish_name TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    houdini_ver TEXT DEFAULT '',
    git_commit TEXT DEFAULT '',
    hip_path TEXT DEFAULT '',
    rop_name TEXT DEFAULT '',
    frame_start INTEGER DEFAULT 1,
    frame_end INTEGER DEFAULT 1,
    disk_mb REAL DEFAULT 0.0,
    thumbnail TEXT DEFAULT '',
    mp4 TEXT DEFAULT '',
    publish_dir TEXT DEFAULT '',
    context_type TEXT DEFAULT '',
    sequence TEXT DEFAULT '',
    shot TEXT DEFAULT '',
    asset_type_f TEXT DEFAULT '',
    asset_name TEXT DEFAULT '',
    tags_json TEXT DEFAULT '[]',
    notes_json TEXT DEFAULT '[]',
    wedge_json TEXT DEFAULT 'null',
    warnings_json TEXT DEFAULT '[]',
    is_orphaned INTEGER DEFAULT 0,
    indexed_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_project ON assets(project);
CREATE INDEX IF NOT EXISTS idx_entity ON assets(entity);
CREATE INDEX IF NOT EXISTS idx_task ON assets(task);
CREATE INDEX IF NOT EXISTS idx_type ON assets(publish_type);
CREATE INDEX IF NOT EXISTS idx_artist ON assets(created_by);
CREATE INDEX IF NOT EXISTS idx_date ON assets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ctx ON assets(context_type, sequence, shot);
"""

_ALLOWED_DISTINCT_COLUMNS = {
    "project", "entity", "task", "publish_type", "publish_name",
    "created_by", "context_type", "sequence", "shot",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_publish_name(record: dict) -> str:
    name = record.get("publish_name", "")
    if name:
        return name
    pub_dir = record.get("_index_path", "")
    if pub_dir:
        parts = Path(pub_dir).parts
        if len(parts) >= 2:
            return parts[-2]
    return ""


def _find_thumbnail(record: dict) -> str:
    thumb = record.get("outputs", {}).get("thumbnail", "")
    if thumb and Path(thumb).exists():
        return thumb
    pub_dir = record.get("_index_path", "")
    if pub_dir:
        candidates = sorted(Path(pub_dir).glob("*.jpg"))
        if candidates:
            return str(candidates[0])
    return ""


def _find_mp4(record: dict) -> str:
    mp4 = record.get("outputs", {}).get("mp4", "")
    if mp4 and Path(mp4).exists():
        return mp4
    pub_dir = record.get("_index_path", "")
    if pub_dir:
        candidates = sorted(Path(pub_dir).glob("*.mp4"))
        if candidates:
            return str(candidates[0])
    return ""


def _record_to_row(record: dict) -> dict:
    import datetime

    uid = record.get("uuid")
    if not uid:
        pub_dir = record.get("_index_path", "")
        uid = f"syn_{abs(hash(pub_dir))}"

    context = record.get("context", {})
    ctx_type = context.get("type", "")
    sequence = context.get("sequence", "")
    shot = context.get("shot", "")
    asset_type_f = context.get("asset_type", "")
    asset_name = context.get("asset", "")

    source = record.get("source", {})
    stats = record.get("stats", {})
    outputs = record.get("outputs", {})

    return {
        "uuid": uid,
        "project": record.get("project", ""),
        "entity": record.get("entity", ""),
        "task": record.get("task", ""),
        "publish_type": record.get("publish_type", ""),
        "publish_name": _extract_publish_name(record),
        "version": int(record.get("version", 1)),
        "created_at": record.get("created_at", ""),
        "created_by": record.get("created_by", ""),
        "houdini_ver": source.get("houdini_version", ""),
        "git_commit": source.get("git_commit", ""),
        "hip_path": source.get("hip", ""),
        "rop_name": source.get("rop", ""),
        "frame_start": int(stats.get("frame_start", 1)),
        "frame_end": int(stats.get("frame_end", 1)),
        "disk_mb": float(stats.get("disk_mb", 0.0)),
        "thumbnail": _find_thumbnail(record),
        "mp4": _find_mp4(record),
        "publish_dir": record.get("_index_path", ""),
        "context_type": ctx_type,
        "sequence": sequence,
        "shot": shot,
        "asset_type_f": asset_type_f,
        "asset_name": asset_name,
        "tags_json": json.dumps(record.get("tags", [])),
        "notes_json": json.dumps(record.get("notes", [])),
        "wedge_json": json.dumps(record.get("wedge", None)),
        "warnings_json": json.dumps(record.get("_warnings", [])),
        "is_orphaned": 1 if record.get("_orphaned") else 0,
        "indexed_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# AssetDatabase
# ---------------------------------------------------------------------------

class AssetDatabase:
    def __init__(self, db_path=None):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert(self, record: dict):
        row = _record_to_row(record)
        cols = list(row.keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        col_list = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO assets ({col_list}) VALUES ({placeholders})"
        with self._conn() as conn:
            conn.execute(sql, row)

    def rebuild_from_index(self, project_folder: str):
        try:
            write_project_index(project_folder)
        except Exception as e:
            logger.warning("Could not rebuild index for %s: %s", project_folder, e)

        index = read_project_index(project_folder)
        if not index:
            logger.warning("No index found for project: %s", project_folder)
            return

        project_name = index.get("project", project_folder)
        with self._conn() as conn:
            conn.execute("DELETE FROM assets WHERE project = ?", (project_name,))

        for record in index.get("publishes", []):
            try:
                self.upsert(record)
            except Exception as e:
                logger.warning("Could not upsert record %s: %s", record.get("uuid"), e)

        logger.info("Rebuilt DB for project %s (%d records)", project_name, len(index.get("publishes", [])))

    def rebuild_all(self):
        for project in load_projects():
            folder = project.get("folder", "")
            if not folder:
                continue
            try:
                self.rebuild_from_index(folder)
            except Exception as e:
                logger.error("Failed to rebuild project %s: %s", folder, e)

    def query_asset_groups(self, filters: dict = None, search: str = "") -> list[dict]:
        filters = filters or {}
        where_clauses = []
        params = {}

        filter_map = {
            "project": "a.project",
            "sequence": "a.sequence",
            "shot": "a.shot",
            "context_type": "a.context_type",
            "publish_type": "a.publish_type",
            "task": "a.task",
            "created_by": "a.created_by",
        }

        for key, col in filter_map.items():
            val = filters.get(key, "")
            if val:
                clause_key = f"f_{key}"
                where_clauses.append(f"{col} = :{clause_key}")
                params[clause_key] = val

        if filters.get("hide_orphaned"):
            where_clauses.append("a.is_orphaned = 0")

        search = (search or "").strip()
        if search:
            terms = search.split()
            for i, term in enumerate(terms):
                pk = f"search_{i}"
                pattern = f"%{term}%"
                where_clauses.append(
                    f"(a.entity LIKE :{pk} OR a.task LIKE :{pk} OR "
                    f"a.publish_type LIKE :{pk} OR a.created_by LIKE :{pk} OR "
                    f"a.tags_json LIKE :{pk} OR a.publish_name LIKE :{pk})"
                )
                params[pk] = pattern

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = f"""
            SELECT * FROM (
                SELECT a.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY a.project, a.entity, a.task, a.publish_type, a.publish_name
                        ORDER BY a.version DESC
                    ) as _rn,
                    COUNT(*) OVER (
                        PARTITION BY a.project, a.entity, a.task, a.publish_type, a.publish_name
                    ) as version_count
                FROM assets a
                {where_sql}
            )
            WHERE _rn = 1
            ORDER BY created_at DESC
        """

        with self._conn() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

        return [dict(r) for r in rows]

    def get_all_versions(self, project: str, entity: str, task: str,
                         publish_type: str, publish_name: str) -> list[dict]:
        sql = """
            SELECT * FROM assets
            WHERE project = :project
              AND entity = :entity
              AND task = :task
              AND publish_type = :publish_type
              AND publish_name = :publish_name
            ORDER BY version DESC
        """
        with self._conn() as conn:
            cursor = conn.execute(sql, {
                "project": project,
                "entity": entity,
                "task": task,
                "publish_type": publish_type,
                "publish_name": publish_name,
            })
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def get_distinct(self, column: str, project: str = "") -> list[str]:
        if column not in _ALLOWED_DISTINCT_COLUMNS:
            raise ValueError(f"Column '{column}' not allowed for get_distinct.")
        if project:
            sql = f"SELECT DISTINCT {column} FROM assets WHERE project = ? AND {column} != '' ORDER BY {column}"
            with self._conn() as conn:
                cursor = conn.execute(sql, (project,))
                return [r[0] for r in cursor.fetchall()]
        else:
            sql = f"SELECT DISTINCT {column} FROM assets WHERE {column} != '' ORDER BY {column}"
            with self._conn() as conn:
                cursor = conn.execute(sql)
                return [r[0] for r in cursor.fetchall()]

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            projects = conn.execute("SELECT COUNT(DISTINCT project) FROM assets").fetchone()[0]
            last_indexed = conn.execute(
                "SELECT MAX(indexed_at) FROM assets"
            ).fetchone()[0] or ""
        return {
            "total": total,
            "projects": projects,
            "last_indexed": last_indexed,
        }
