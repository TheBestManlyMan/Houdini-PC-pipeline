"""
Publish product builder.

Scans a publish directory, validates outputs deterministically, and returns
a fully constructed PublishProduct.  No Houdini API, no UI logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .publish_schema import (
    SCHEMA_VERSION,
    Preview,
    PublishAudit,
    PublishPaths,
    PublishProduct,
    PublishStats,
    Representation,
)

# ---------------------------------------------------------------------------
# Extension → representation type mapping
# ---------------------------------------------------------------------------

_EXT_REP_TYPE: dict[str, str] = {
    ".jpg":     "jpg_sequence",
    ".jpeg":    "jpg_sequence",
    ".png":     "png_sequence",
    ".mp4":     "mp4",
    ".usd":     "usd",
    ".usda":    "usd",
    ".usdc":    "usd",
    ".exr":     "exr",
    ".bgeo":    "bgeo",
    ".bgeo.sc": "bgeo",
    ".vdb":     "vdb",
    ".abc":     "abc",
}

# Sequence extensions — files that can form frame sequences
_SEQUENCE_REP_TYPES = frozenset({"jpg_sequence", "png_sequence", "exr", "bgeo", "vdb"})

# Frame filename pattern: prefix_v001.0001.ext  (4-digit zero-padded frame)
_FRAME_RE = re.compile(r"^(.+_v\d{3}[._])(\d{4})(\..+)$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _file_ext(path: Path) -> str:
    """Return canonical extension, handling double extensions like .bgeo.sc."""
    name = path.name.lower()
    if name.endswith(".bgeo.sc"):
        return ".bgeo.sc"
    return "".join(path.suffixes).lower()


def _rep_type(path: Path) -> Optional[str]:
    return _EXT_REP_TYPE.get(_file_ext(path))


def _scan_dir(directory: Path) -> tuple[dict, dict]:
    """
    Return (sequences, singles).

    sequences: {(prefix, suffix): {frame_int: Path}}
    singles:   {rep_type: [Path]}
    """
    sequences: dict[tuple, dict[int, Path]] = {}
    singles: dict[str, list[Path]] = {}

    for f in sorted(directory.iterdir()):
        if not f.is_file():
            continue
        m = _FRAME_RE.match(f.name)
        if m:
            key = (m.group(1), m.group(3))
            sequences.setdefault(key, {})[int(m.group(2))] = f
        else:
            rt = _rep_type(f)
            if rt:
                singles.setdefault(rt, []).append(f)

    return sequences, singles


def _validate_and_sort_sequence(
    frames: dict[int, Path],
    frame_start: Optional[int],
    frame_end: Optional[int],
    rep_type: str,
) -> list[str]:
    """
    Validate frame completeness and return sorted absolute file list.

    If frame_start/frame_end are provided, the exact set {frame_start..frame_end}
    must be present.  Otherwise, checks for gaps in the detected range.
    Raises ValueError on any gap or mismatch.
    """
    if not frames:
        raise ValueError(f"Empty {rep_type} sequence — no frames found.")

    actual = set(frames.keys())

    if frame_start is not None and frame_end is not None:
        expected = set(range(frame_start, frame_end + 1))
        missing = expected - actual
        extra = actual - expected
        errors = []
        if missing:
            sample = sorted(missing)[:6]
            errors.append(f"missing frames {sample} (expected {frame_start}–{frame_end})")
        if extra:
            sample = sorted(extra)[:6]
            errors.append(f"unexpected frames {sample}")
        if errors:
            raise ValueError(f"Incomplete {rep_type} sequence: " + "; ".join(errors))
    else:
        # No expected range — just check for gaps within detected min..max
        lo, hi = min(actual), max(actual)
        expected = set(range(lo, hi + 1))
        missing = expected - actual
        if missing:
            sample = sorted(missing)[:6]
            raise ValueError(
                f"Gap in {rep_type} sequence: missing frames {sample} "
                f"(detected range {lo}–{hi})"
            )

    return [str(frames[n]) for n in sorted(frames.keys())]


def _dir_size_bytes(directory: Path) -> int:
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_publish_product(pub_dir, ctx: dict) -> PublishProduct:
    """
    Scan pub_dir, validate outputs, and return a fully constructed PublishProduct.

    Required ctx keys:
        entity          str
        task            str
        publish_name    str
        version         int
        product_type    str  — "asset" | "flipbook" | "render"
        published_by    str
        published_at    str  — ISO 8601 timestamp

    Optional ctx keys:
        frame_start     int  — validate sequence completeness when provided with frame_end
        frame_end       int
        animated        bool — inferred from frame_start/frame_end when omitted
        hip_snapshot    str | None
        preview_dir     str | Path | None — where jpg/mp4 live for asset/render publishes
        expect_mp4      bool — default True for flipbook, False otherwise
        usd_path        str | None — explicit USD file path (render publishes)

    Raises ValueError if any required output is missing, incomplete, or has gaps.
    Returns a PublishProduct (never a dict).
    """
    pub_dir = Path(pub_dir)
    if not pub_dir.is_dir():
        raise ValueError(f"Publish directory does not exist: {pub_dir}")

    entity       = ctx["entity"]
    task         = ctx["task"]
    publish_name = ctx["publish_name"]
    version      = ctx["version"]
    product_type = ctx["product_type"]
    published_by = ctx["published_by"]
    published_at = ctx["published_at"]
    hip_snapshot = ctx.get("hip_snapshot")

    frame_start  = ctx.get("frame_start")
    frame_end    = ctx.get("frame_end")
    animated     = ctx.get("animated", frame_start is not None and frame_end is not None)
    preview_dir  = ctx.get("preview_dir")
    if preview_dir is not None:
        preview_dir = Path(preview_dir)
    expect_mp4   = ctx.get("expect_mp4", product_type == "flipbook")
    usd_path_ctx = ctx.get("usd_path")

    representations: list[Representation] = []

    # ------------------------------------------------------------------
    # Scan primary publish directory
    # ------------------------------------------------------------------
    pub_seqs, pub_singles = _scan_dir(pub_dir)

    for (prefix, suffix), frames in pub_seqs.items():
        rt = _EXT_REP_TYPE.get(suffix)
        if rt is None:
            continue
        fs = frame_start if animated else None
        fe = frame_end   if animated else None
        file_list = _validate_and_sort_sequence(frames, fs, fe, rt)
        representations.append(Representation(
            type=rt, files=file_list, frame_start=fs, frame_end=fe
        ))

    for rt, paths in pub_singles.items():
        representations.append(Representation(
            type=rt, files=sorted(str(p) for p in paths)
        ))

    # ------------------------------------------------------------------
    # Scan preview directory (asset / render — separate location from pub_dir)
    # ------------------------------------------------------------------
    preview_jpg_files: list[str] = []
    preview_mp4_path: Optional[str] = None

    if preview_dir is not None and preview_dir.is_dir():
        prev_seqs, prev_singles = _scan_dir(preview_dir)

        for (prefix, suffix), frames in prev_seqs.items():
            rt = _EXT_REP_TYPE.get(suffix)
            if rt not in ("jpg_sequence", "png_sequence"):
                continue
            fs = frame_start if animated else None
            fe = frame_end   if animated else None
            file_list = _validate_and_sort_sequence(frames, fs, fe, rt)
            preview_jpg_files = file_list
            representations.append(Representation(
                type=rt, files=file_list, frame_start=fs, frame_end=fe
            ))

        if "mp4" in prev_singles:
            preview_mp4_path = str(sorted(prev_singles["mp4"])[0])
            representations.append(Representation(type="mp4", files=[preview_mp4_path]))

    elif product_type == "flipbook":
        # For flipbook pub_dir IS the preview dir — extract from already-scanned reps
        for rep in representations:
            if rep.type in ("jpg_sequence", "png_sequence") and not preview_jpg_files:
                preview_jpg_files = rep.files
            elif rep.type == "mp4" and preview_mp4_path is None:
                preview_mp4_path = rep.files[0]

    # ------------------------------------------------------------------
    # Handle explicit USD path supplied via ctx (render publishes)
    # ------------------------------------------------------------------
    if usd_path_ctx:
        usd_file = Path(usd_path_ctx)
        already_have_usd = any(r.type == "usd" for r in representations)
        if usd_file.exists() and not already_have_usd:
            representations.append(Representation(type="usd", files=[usd_path_ctx]))

    # ------------------------------------------------------------------
    # Fail-fast validation
    # ------------------------------------------------------------------
    if not representations:
        raise ValueError(f"No recognisable output files found in: {pub_dir}")

    if product_type == "flipbook":
        seq_reps = [r for r in representations if r.type in ("jpg_sequence", "png_sequence")]
        if not seq_reps:
            raise ValueError(
                f"Flipbook publish requires a jpg/png image sequence in: {pub_dir}"
            )

    elif product_type in ("asset", "render"):
        primary_reps = [
            r for r in representations
            if r.type not in ("jpg_sequence", "png_sequence", "mp4")
        ]
        if not primary_reps:
            raise ValueError(
                f"No primary output files (geo/exr/usd) found in: {pub_dir}"
            )

    if product_type == "render":
        usd_reps = [r for r in representations if r.type == "usd"]
        if not usd_reps:
            expected_path = usd_path_ctx or "(unknown)"
            raise ValueError(
                f"Render publish requires a USD output file. Expected: {expected_path}"
            )

    if expect_mp4 and not preview_mp4_path:
        raise ValueError(
            "MP4 preview expected but not found. "
            f"Check: {preview_dir or pub_dir}"
        )

    # ------------------------------------------------------------------
    # Build schema objects
    # ------------------------------------------------------------------

    # Primary file = first file of the first non-preview representation
    primary_reps_ordered = [
        r for r in representations
        if r.type not in ("jpg_sequence", "png_sequence", "mp4")
    ] or representations
    primary_file = primary_reps_ordered[0].files[0] if primary_reps_ordered[0].files else ""

    paths = PublishPaths(
        root=str(pub_dir),
        primary=primary_file,
        working=hip_snapshot,
    )

    thumbnail = preview_jpg_files[0] if preview_jpg_files else None
    preview = Preview(thumbnail=thumbnail, mp4=preview_mp4_path)

    # Frame count from first sequence representation
    frame_count = 0
    for rep in representations:
        if rep.type in _SEQUENCE_REP_TYPES:
            if rep.frame_start is not None and rep.frame_end is not None:
                frame_count = rep.frame_end - rep.frame_start + 1
            else:
                frame_count = len(rep.files)
            break

    try:
        total_bytes = _dir_size_bytes(pub_dir)
        if preview_dir is not None and preview_dir.is_dir():
            total_bytes += _dir_size_bytes(preview_dir)
        size_bytes: Optional[int] = total_bytes
    except Exception:
        size_bytes = None

    stats = PublishStats(frame_count=frame_count, size_bytes=size_bytes)

    audit = PublishAudit(
        published_by=published_by,
        published_at=published_at,
        hip_snapshot=hip_snapshot,
    )

    return PublishProduct(
        schema_version=SCHEMA_VERSION,
        entity=entity,
        task=task,
        publish_name=publish_name,
        version=version,
        product_type=product_type,
        paths=paths,
        representations=representations,
        preview=preview,
        stats=stats,
        audit=audit,
    )
