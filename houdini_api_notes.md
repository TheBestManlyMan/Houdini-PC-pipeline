# Houdini Python API Notes

Verified method signatures and gotchas for Houdini 21.0.631 (Python 3.11, Windows).
**Always check this file before writing any `hou.*` call.**

---

## hou.hipFile — Session File

```python
hou.hipFile.path()             # Returns current hip path as string
hou.hipFile.name()             # Returns just the filename (no directory)
hou.hipFile.save(path)         # Save to path AND set as active file (like File → Save As)
                               # ⚠️ NOT saveAs() — that method does not exist
hou.hipFile.save()             # Save in place (no arg = overwrite current file)
hou.hipFile.load(path)         # Open a hip file
hou.hipFile.hasUnsavedChanges() # Returns bool
```

---

## hou.node() — Node Access

```python
hou.node("/obj/mynode")        # Get node by absolute path — returns None if not found
hou.selectedNodes()            # List of currently selected nodes — use [0] to get first
                               # ⚠️ Never hardcode node paths — always use selectedNodes() or traverse

node.path()                    # Absolute path string
node.name()                    # Node name only
node.parent()                  # Parent node
node.children()                # Tuple of child nodes
node.type().name()             # Node type string e.g. "rop_geometry"
node.inputs()                  # Tuple of input nodes (None where unconnected)
node.outputs()                 # Tuple of output nodes
node.isInsideLockedHDA()       # True if inside a locked HDA — cannot set parms directly
node.destroy()                 # Delete the node
```

---

## hou.Parm — Parameters

```python
node.parm("parm_name")         # Get a single parm — returns None if doesn't exist
node.parmTuple("parm_name")    # Get a tuple parm (e.g. xyz vector)
node.parms()                   # All parms on node

parm.set(value)                # Set value (int, float, str)
parm.eval()                    # Evaluate and return value
parm.evalAsString()            # Evaluate as string (expands $HIP etc.)
parm.evalAsInt()               # Evaluate as int
parm.evalAsFloat()             # Evaluate as float
parm.setExpression("$HIP")     # Set a Houdini expression string
parm.expression()              # Get current expression string (raises if no expression)
parm.hasExpression()           # Check before calling expression()
parm.deleteAllKeyframes()      # Remove all keyframes / expressions
parm.pressButton()             # Trigger a button parm callback
                               # ⚠️ COP button parms need node.cook(force=True) first
                               #    or the callback silently does nothing (H21 bug)

node.cook(force=True)          # Force cook before pressButton() on COP nodes
```

---

## hou.hscript / Expressions

```python
hou.hscriptExpression("$HIP")           # Evaluate an hscript expression — returns value
hou.hscriptStringExpression("$HIPNAME") # Returns string result
hou.expandString("$HIP/cache")          # Expand variables in a string path
                                        # ⚠️ Use expandString for paths, not hscriptExpression
```

---

## hou.Node — Creating and Finding Nodes

```python
parent.createNode("rop_geometry", "OUT_smoke")   # Create child node
parent.findChildren(node_type="rop_geometry")     # Recursively find by type — returns list
node.copyTo(dest_parent)                          # Copy node to another parent
```

---

## hou.text / UI

```python
hou.ui.displayMessage("Done!")                    # Simple dialog
hou.ui.displayMessage("Error", severity=hou.severityType.Error)
choice = hou.ui.displayConfirmation("Continue?")  # Returns True/False
result = hou.ui.readInput("Enter task name:")      # Returns (button_idx, string)
hou.ui.setStatusMessage("Processing...")           # Bottom status bar
```

---

## hou.frame / Time

```python
hou.frame()                    # Current frame (float)
hou.intFrame()                 # Current frame as int
hou.fps()                      # Scene FPS
hou.playbar.frameRange()       # Returns (start, end) tuple — global frame range
hou.playbar.playbackRange()    # Returns (start, end) tuple — playback range
```

---

## hou.putenv / Environment

```python
hou.putenv("MY_VAR", "value")  # Set env var for this Houdini session
hou.getenv("MY_VAR")           # Get env var (returns None if not set)
hou.expandString("$MY_VAR")    # Expand in a path string
```

---

## hou.HDAModule — HDA Python Module

```python
node.hdaModule()               # Access the HDA's Python module
node.hdaModule().my_function() # Call a function defined in the HDA PythonModule
hou.phm()                      # Shortcut for current HDA's Python module
                               # (only valid inside HDA callback scripts)
```

---

## COP Nodes (H21 Gotchas)

```python
# ⚠️ In Houdini 21, COP button parms silently do nothing without a force cook first:
node.cook(force=True)
node.parm("addaovs").pressButton()

# ⚠️ colorspace parm uses token "ocio", NOT the display label string:
node.parm("colorspace").set("ocio")

# CopNet must live at obj/ level (sibling of HDA), NOT inside a locked HDA
```

---

## TOPs / PDG

```python
work_item.attribValue("attr_name")          # Read work item attribute
work_item.setAttrib("attr_name", value)     # Write attribute (string/int/float)
work_item.data.setString("key", value, 0)   # PDG data store alternative

# ⚠️ partitionItems is unreliable in this PDG context.
# Always read ROP nodes directly from the HDA multiparm instead.

# Entity type must be stamped at work item GENERATION time, not re-parsed downstream
```

---

## Common Patterns Used in This Pipeline

```python
# Get current hip version number
import re, hou
hip = hou.hipFile.name()
m = re.search(r"_v(\d{3})\.", hip, re.IGNORECASE)
version = int(m.group(1)) if m else 1

# Get selected node safely
nodes = hou.selectedNodes()
if not nodes:
    hou.ui.displayMessage("Select a node first.", severity=hou.severityType.Error)
else:
    node = nodes[0]

# Reload sg_pipeline after editing on disk
import importlib, sg_pipeline
importlib.reload(sg_pipeline)
```

---

## What Does NOT Exist (Common Mistakes)

| Wrong | Right |
|-------|-------|
| `hou.hipFile.saveAs(path)` | `hou.hipFile.save(path)` |
| `hou.selectedNode()` | `hou.selectedNodes()[0]` |
| `parm.getValue()` | `parm.eval()` |
| `node.getChildren()` | `node.children()` |
| `hou.getFrame()` | `hou.frame()` |
