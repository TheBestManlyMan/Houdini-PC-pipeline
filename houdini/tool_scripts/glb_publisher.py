"""
Houdini shelf tool — Export selected SOP geometry to a GLB asset.

Usage:
  Select a SOP node (or geometry object), then run this shelf script.
  A dialog will prompt for project, asset name, and tags.

Published structure:
  {shows_root}/assets/{project}/{asset_name}/
      asset.glb
      thumbnail.jpg      (Houdini viewport snapshot)
      metadata.json

Requirements:
  - Houdini 19.5+
  - gltf-export (ROP GLTF ROP or fbx2gltf / direct glTF from houdini)
  - Python packages: (standard library only, no pip needed inside Houdini)
"""

import hou
import os
import sys
import json
import datetime
import re
import subprocess
import tempfile
from pathlib import Path


# ---- Load pipeline config ------------------------------------------------

def _pipeline_root():
    env = os.environ.get("HOUDINI_PIPELINE_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


def _load_config():
    cfg_path = _pipeline_root() / "pipeline_config.json"
    with open(cfg_path) as f:
        return json.load(f)


def _shows_root():
    cfg = _load_config()
    return Path(cfg["projects_root"])


def _sanitize(name: str) -> str:
    """Make a string safe for a directory/filename."""
    name = name.strip().lower()
    name = re.sub(r"[^\w\-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "asset"


# ---- UI dialog (Qt) -------------------------------------------------------

def _show_dialog():
    """Show a simple Houdini Qt dialog to collect publish parameters."""
    from PySide2 import QtWidgets, QtCore

    class PublishDialog(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Publish 3D Asset (GLB)")
            self.setMinimumWidth(360)
            layout = QtWidgets.QVBoxLayout(self)

            form = QtWidgets.QFormLayout()

            self.project_edit = QtWidgets.QLineEdit("test")
            form.addRow("Project:", self.project_edit)

            self.name_edit = QtWidgets.QLineEdit()
            self.name_edit.setPlaceholderText("e.g. hero_tank")
            form.addRow("Asset name:", self.name_edit)

            self.author_edit = QtWidgets.QLineEdit(os.environ.get("USER", "artist"))
            form.addRow("Author:", self.author_edit)

            self.tags_edit = QtWidgets.QLineEdit()
            self.tags_edit.setPlaceholderText("comma-separated: fx, sim, vehicle")
            form.addRow("Tags:", self.tags_edit)

            self.desc_edit = QtWidgets.QTextEdit()
            self.desc_edit.setPlaceholderText("Optional description")
            self.desc_edit.setMaximumHeight(60)
            form.addRow("Description:", self.desc_edit)

            self.overwrite_cb = QtWidgets.QCheckBox("Overwrite existing")
            self.overwrite_cb.setChecked(True)
            form.addRow("", self.overwrite_cb)

            layout.addLayout(form)

            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            )
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def result_data(self):
            return {
                "project": _sanitize(self.project_edit.text()),
                "asset_name": _sanitize(self.name_edit.text()),
                "author": self.author_edit.text().strip() or os.environ.get("USER", "artist"),
                "tags": [t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
                "description": self.desc_edit.toPlainText().strip(),
                "overwrite": self.overwrite_cb.isChecked(),
            }

    main_window = hou.qt.mainWindow()
    dialog = PublishDialog(main_window)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        print("[GLB Publisher] Cancelled.")
        return None
    return dialog.result_data()


# ---- Geometry helpers -------------------------------------------------------

def _get_geometry_node():
    """Return the first selected SOP or OBJ node."""
    selected = hou.selectedNodes()
    for node in selected:
        if node.type().category().name() in ("Sop", "Object"):
            return node
    # Fall back to /obj/geo1 if nothing selected
    root_obj = hou.node("/obj")
    if root_obj:
        for child in root_obj.children():
            if child.type().name() in ("geo", "object_merge"):
                return child
    return None


def _count_polygons(geo_node) -> int:
    """Count total polygons in the node's geometry."""
    try:
        geo = geo_node.geometry() if hasattr(geo_node, "geometry") else geo_node.displayNode().geometry()
        return geo.intrinsicValue("primitivecount")
    except Exception:
        return 0


def _get_frame_range():
    """Return (start, end) from the current Houdini timeline."""
    return (int(hou.playbar.playbackRange()[0]), int(hou.playbar.playbackRange()[1]))


def _is_animated(geo_node) -> bool:
    """Heuristic: check if node has time-dependent expressions."""
    try:
        return geo_node.isTimeDependent()
    except Exception:
        return False


# ---- Export -----------------------------------------------------------------

def _export_glb(geo_node, out_path: Path, frame_range: tuple, is_animated: bool):
    """
    Export geometry to GLB using Houdini's GLTF ROP.
    Falls back to a FBX-to-GLB conversion via fbx2gltf if available.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Try Houdini GLTF ROP first (Houdini 19.5+)
    gltf_rop = _try_gltf_rop(geo_node, out_path, frame_range, is_animated)
    if gltf_rop:
        return

    # Fallback: export FBX then convert
    print("[GLB Publisher] GLTF ROP unavailable, trying FBX → GLB conversion…")
    _export_via_fbx(geo_node, out_path, frame_range, is_animated)


def _try_gltf_rop(geo_node, out_path: Path, frame_range: tuple, is_animated: bool) -> bool:
    """Attempt export using rop_gltf or sopnet/export nodes."""
    obj = geo_node if geo_node.type().category().name() == "Object" else geo_node.parent()

    # Check if a GLTF ROP exists or can be created in /out
    rop_parent = hou.node("/out")
    if rop_parent is None:
        return False

    rop_type = "rop_gltf"
    if not any(t.name() == rop_type for t in hou.ropNodeTypeCategory().nodeTypes().values()):
        return False

    tmp_rop = rop_parent.createNode(rop_type, "__glb_publisher_tmp__")
    try:
        tmp_rop.parm("soppath").set(geo_node.path())
        tmp_rop.parm("file").set(str(out_path))

        if is_animated:
            tmp_rop.parm("f1").set(frame_range[0])
            tmp_rop.parm("f2").set(frame_range[1])
            tmp_rop.parm("initsim").set(False)

        tmp_rop.render()
        print(f"[GLB Publisher] GLTF ROP export complete → {out_path}")
        return True
    except hou.OperationFailed as e:
        print(f"[GLB Publisher] GLTF ROP failed: {e}")
        return False
    finally:
        tmp_rop.destroy()


def _export_via_fbx(geo_node, out_path: Path, frame_range: tuple, is_animated: bool):
    """Export FBX then convert to GLB with fbx2gltf or gltf-pipeline."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        fbx_path = Path(tmp_dir) / "export.fbx"

        rop_parent = hou.node("/out")
        fbx_rop = rop_parent.createNode("filmboxfbx", "__glb_publisher_fbx__")
        try:
            fbx_rop.parm("sopoutput").set(str(fbx_path))
            obj = geo_node if geo_node.type().category().name() == "Object" else geo_node.parent()
            fbx_rop.parm("startnode").set(obj.path())
            fbx_rop.parm("exportkind").set(0)  # FBX
            if is_animated:
                fbx_rop.parm("f1").set(frame_range[0])
                fbx_rop.parm("f2").set(frame_range[1])
            fbx_rop.render()
        finally:
            fbx_rop.destroy()

        # Try fbx2gltf
        converters = ["fbx2gltf", "FBX2glTF"]
        for cmd in converters:
            try:
                subprocess.run(
                    [cmd, "-i", str(fbx_path), "-o", str(out_path), "--binary"],
                    check=True, capture_output=True
                )
                print(f"[GLB Publisher] FBX→GLB via {cmd} complete → {out_path}")
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue

        hou.ui.displayMessage(
            "Export failed: no GLB converter found.\n"
            "Install fbx2gltf or enable the GLTF ROP.",
            severity=hou.severityType.Error
        )
        raise RuntimeError("GLB export failed — no converter available")


# ---- Thumbnail --------------------------------------------------------------

def _capture_thumbnail(out_path: Path):
    """Capture a viewport screenshot as thumbnail.jpg."""
    try:
        desktop = hou.ui.curDesktop()
        if desktop is None:
            return
        pane = None
        for pt in desktop.paneTabs():
            if pt.type() == hou.paneTabType.SceneViewer:
                pane = pt
                break
        if pane is None:
            return

        thumb_path = str(out_path)
        pane.curViewport().snapshot(thumb_path)
        print(f"[GLB Publisher] Thumbnail saved → {thumb_path}")
    except Exception as e:
        print(f"[GLB Publisher] Thumbnail capture failed (non-fatal): {e}")


# ---- Main -------------------------------------------------------------------

def main():
    params = _show_dialog()
    if not params:
        return

    if not params["asset_name"]:
        hou.ui.displayMessage("Asset name cannot be empty.", severity=hou.severityType.Error)
        return

    geo_node = _get_geometry_node()
    if geo_node is None:
        hou.ui.displayMessage(
            "No geometry node selected.\nSelect a SOP or Object node first.",
            severity=hou.severityType.Error
        )
        return

    shows = _shows_root()
    asset_dir = shows / "assets" / params["project"] / params["asset_name"]

    if asset_dir.exists() and not params["overwrite"]:
        hou.ui.displayMessage(
            f"Asset already exists at:\n{asset_dir}\n\nEnable 'Overwrite' to replace it.",
            severity=hou.severityType.Warning
        )
        return

    asset_dir.mkdir(parents=True, exist_ok=True)

    frame_range = _get_frame_range()
    is_anim = _is_animated(geo_node)
    polycount = _count_polygons(geo_node)

    print(f"[GLB Publisher] Publishing '{params['asset_name']}' → {asset_dir}")
    print(f"[GLB Publisher]   Frames: {frame_range}, Animated: {is_anim}, Polys: {polycount}")

    # 1. Export GLB
    glb_path = asset_dir / "asset.glb"
    try:
        _export_glb(geo_node, glb_path, frame_range, is_anim)
    except Exception as e:
        hou.ui.displayMessage(f"GLB export failed:\n{e}", severity=hou.severityType.Error)
        return

    # 2. Capture thumbnail
    _capture_thumbnail(asset_dir / "thumbnail.jpg")

    # 3. Write metadata.json
    meta = {
        "name": params["asset_name"].replace("_", " ").title(),
        "author": params["author"],
        "created": datetime.datetime.utcnow().isoformat() + "Z",
        "houdini_version": hou.applicationVersionString(),
        "frame_range": list(frame_range),
        "tags": params["tags"],
        "animations": ["Main"] if is_anim else [],
        "polycount": polycount,
        "project": params["project"],
        "asset_name": params["asset_name"],
        "description": params["description"],
        "source_node": geo_node.path(),
    }
    meta_path = asset_dir / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[GLB Publisher] metadata.json written → {meta_path}")

    hou.ui.displayMessage(
        f"Published successfully!\n\n"
        f"Asset: {params['asset_name']}\n"
        f"Project: {params['project']}\n"
        f"Location: {asset_dir}\n\n"
        f"Refresh the 3D Assets browser to see it.",
        severity=hou.severityType.Message
    )


# Run when used as a shelf tool
main()
