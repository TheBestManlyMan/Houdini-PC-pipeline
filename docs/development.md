# Development Conventions

Engineering rules for working on this codebase. Separate from Claude-specific instructions (those live in `CLAUDE.md`).

---

## Core rule: `python/pipeline/` owns all logic

UI scripts, the API server, and Houdini tool scripts are thin layers. They call `pipeline.*` functions. They do not build paths, compute version numbers, or construct metadata.

```python
# correct — in publisher.py
import pipeline
version = pipeline.get_next_publish_version(...)
path = pipeline.build_publish_path(...)
pipeline.write_metadata(path, pipeline.build_metadata(...))

# wrong — in publisher.py
version = len(os.listdir(publish_dir)) + 1          # no — scan correctly
path = f"{projects_root}/{project}/{seq}/..."        # no — use pipeline.build_publish_path()
```

---

## Module responsibilities

| Module | Owns | Does NOT own |
|--------|------|--------------|
| `paths.py` | All path construction | Filesystem operations |
| `versioning.py` | Disk-based version scanning | Path building |
| `publish.py` | Hip naming, publish path assembly | Versioning logic |
| `cache.py` | Cache dir creation, cache file naming | Publish paths |
| `metadata.py` | metadata.json schema v2 read/write | Path building |
| `indexer.py` | Scanning dirs → publishes.json | Metadata schema |
| `validation.py` | Input validation for user data | Business logic |
| `publish_schema.py` | `PublishProduct` dataclass contract | I/O, filesystem |
| `publish_product.py` | Building `PublishProduct` from disk | Schema definition |
| `database.py` | SQLite cache for Asset Browser | Canonical data |
| `config.py` | `pipeline_config.json` loading | Any other logic |
| `entities.py` | `projects.json` CRUD | Any other logic |
| `ffmpeg.py` | ffmpeg subprocess calls | Path building |
| `flipbook.py` | Houdini `hou.*` viewport capture | Path building |

---

## Path rules

- Never use string concatenation or f-strings to build pipeline paths in UI code.
- Always use `pipeline.shot_fx_root()`, `pipeline.build_publish_path()`, etc.
- Both contexts (shot and asset) must always be supported in path functions.

**Shot context:**

```python
pipeline.shot_fx_root(project="my-short", seq="SQ010", shot="0010")
# → /projects/shows/my-short/SQ010/0010/FX
```

**Asset context:**

```python
pipeline.asset_fx_root(project="my-short", asset_type="character", asset="hero")
# → /projects/shows/my-short/assets/character/hero/FX
```

---

## Naming conventions

### Files

| Type | Pattern |
|------|---------|
| Hip file | `{entity}_fx_{task}_v001.hip` |
| Cache geo | `{entity}_fx_{task}_v001.$F4.bgeo.sc` |
| Cache VDB | `{entity}_fx_{task}_v001.$F4.vdb` |
| Cache Alembic | `{entity}_fx_{task}_v001.abc` |
| USD | `{entity}_fx_{task}_v001.usd` |
| Flipbook frame | `{entity}_fx_flipbook_v001.$F4.jpg` |
| MP4 preview | `{entity}_fx_{task}_v001.mp4` |

### Identifiers

- **Version:** 3-digit zero-padded (`v001`, `v002`, …). Always from `pipeline.version_str(n)`.
- **Task:** Lowercase, digits, hyphens only. No spaces, no underscores. Use `naming_conventions.validate_task()` on user input.
- **Entity:** Shot code (`SQ010_0010`) or asset name (`hero`). Underscores for shots, plain lowercase for assets.

---

## Versioning rule

Version numbers come from scanning the disk. Never compute them from a counter, a database value, or any other source.

```python
# correct
version = pipeline.get_next_publish_version(publish_dir)

# wrong
version = config.get("last_version", 0) + 1
version = db.query("SELECT MAX(version) FROM assets") + 1
```

If the scan returns the wrong version, there is a real file on disk causing it. Investigate rather than overriding.

---

## Import patterns

From Houdini shelf scripts, UI dialogs, and the API server:

```python
import pipeline                          # preferred — single import
pipeline.shot_fx_root(...)

from pipeline import build_publish_path  # also fine for specific imports
```

Within `python/pipeline/` submodules, use relative imports:

```python
from .config import projects_root
from .paths import shot_fx_root
```

Do not do circular imports. The dependency order is:

```
config → (no deps)
entities → config
paths → config
versioning → paths
publish → config, paths, versioning
cache → config, paths, versioning
metadata → config
indexer → config, entities, paths, metadata
publish_product → publish_schema
database → config, entities, indexer
```

---

## Testing

Tests live in `tests/test_pipeline.py`. They test the `python/pipeline/` package only — no Houdini API, no UI, no network.

Run:

```bash
python3 -m pytest tests/
```

After editing any `python/pipeline/` module: check if the tests need updating. A new path builder function needs at least one test covering both shot and asset contexts. A new metadata field needs a round-trip test.

Tests use `tmp_path` (pytest fixture) for all filesystem operations. No tests should read from or write to a real projects directory.

---

## Adding a new pipeline function

1. Add it to the appropriate submodule in `python/pipeline/`.
2. Export it from `python/pipeline/__init__.py`.
3. Add it to the `__all__` list in `__init__.py`.
4. Write at least one test in `tests/test_pipeline.py`.
5. Document it in `docs/pipeline_api.md`.

---

## Metadata schema

Current version: **2**. Defined in `python/pipeline/metadata.py`.

When adding a new metadata field:

1. Add it to `build_metadata()` with a sensible default.
2. Handle the missing key gracefully in `read_metadata()` (old files on disk will not have it).
3. If the field is critical and old files should be upgraded, add an upgrade path in `build_metadata_from_legacy()`.
4. Bump `schema_version` only for breaking changes — adding optional fields with defaults is backward-compatible.

---

## API server conventions

- All routes are in `python/api_server.py`. Do not split into multiple router files.
- The server is stateless. Each request reads from disk (or the cached `publishes.json`).
- Absolute filesystem paths must never appear in API responses. Always rewrite via `_mediafy()`.
- Do not add authentication. The server is only reachable over Tailscale.

---

## Web gallery conventions

- One app (`web/src/App.jsx`). Three surfaces: Gallery, 3D Assets, Manager.
- Do not add new surfaces without a strong reason and explicit agreement.
- Business logic (path construction, versioning) does not belong in React components. Components fetch from the API and display.
- Heavy dependencies (Three.js) must be lazy-loaded.
- Responsive layout via CSS only. No separate mobile component tree.

---

## The `archive/` directory

Code in `archive/` is preserved for reference but is not part of the active pipeline. Do not import from it. Do not modify it. If you need to recover something from it, copy the file out and update it before using.

Currently archived:
- `publish_gallery.py` — legacy static HTML gallery generator (superseded by the React gallery)
- `gallery_launch.py` — Houdini shelf button that launched the static gallery
