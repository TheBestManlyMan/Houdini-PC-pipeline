"""
Canonical publish schema v1.

Defines the strict data contract for all pipeline publishes.
No Houdini API calls, no UI logic, no filesystem scanning.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

SCHEMA_VERSION = 1
VALID_PRODUCT_TYPES = frozenset({"asset", "flipbook", "render"})


@dataclass
class Representation:
    """A single output format within a publish."""
    type: str       # jpg_sequence | png_sequence | mp4 | usd | exr | bgeo | vdb | abc
    files: list     # sorted explicit absolute file paths — no glob patterns
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    fps: Optional[float] = None

    def to_dict(self) -> dict:
        d: dict = {"type": self.type, "files": self.files}
        if self.frame_start is not None:
            d["frame_start"] = self.frame_start
        if self.frame_end is not None:
            d["frame_end"] = self.frame_end
        if self.fps is not None:
            d["fps"] = self.fps
        return d


@dataclass
class Preview:
    """Preview assets for gallery display."""
    thumbnail: Optional[str] = None   # absolute path to first frame or thumbnail.jpg
    mp4: Optional[str] = None         # absolute path to mp4 preview

    def to_dict(self) -> dict:
        return {"thumbnail": self.thumbnail, "mp4": self.mp4}


@dataclass
class PublishPaths:
    """Grouped path references for a publish."""
    root: str                   # versioned publish directory (absolute)
    primary: str                # main output file — first file when sequence
    working: Optional[str] = None  # hip snapshot path

    def to_dict(self) -> dict:
        d: dict = {"root": self.root, "primary": self.primary}
        if self.working is not None:
            d["working"] = self.working
        return d


@dataclass
class PublishAudit:
    """Provenance for a publish."""
    published_by: str
    published_at: str           # ISO 8601 timestamp
    hip_snapshot: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {"published_by": self.published_by, "published_at": self.published_at}
        if self.hip_snapshot is not None:
            d["hip_snapshot"] = self.hip_snapshot
        return d


@dataclass
class PublishStats:
    """Computed statistics for a publish."""
    frame_count: int = 0
    size_bytes: Optional[int] = None

    def to_dict(self) -> dict:
        d: dict = {"frame_count": self.frame_count}
        if self.size_bytes is not None:
            d["size_bytes"] = self.size_bytes
        return d


@dataclass
class PublishProduct:
    """
    Canonical publish schema v1.

    Single source of truth for a pipeline publish record.
    Produced by build_publish_product(); serialised by to_dict() and written
    to metadata.json; consumed read-only by the gallery.
    """
    schema_version: int
    entity: str
    task: str
    publish_name: str
    version: int
    product_type: str           # asset | flipbook | render
    paths: PublishPaths
    representations: list       # list[Representation]
    preview: Preview
    stats: PublishStats
    audit: PublishAudit

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "entity": self.entity,
            "task": self.task,
            "publish_name": self.publish_name,
            "version": self.version,
            "product_type": self.product_type,
            "paths": self.paths.to_dict(),
            "representations": [r.to_dict() for r in self.representations],
            "preview": self.preview.to_dict(),
            "stats": self.stats.to_dict(),
            "audit": self.audit.to_dict(),
        }
