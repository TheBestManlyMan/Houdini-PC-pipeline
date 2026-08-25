"""
Check a constraints file the way Kimodo will read it.

Runs in the **Kimodo venv** (it imports torch and kimodo), never in Houdini::

    ~/Projects/kimodo/.venv/bin/python verify_constraints.py \
        /path/to/clip_constraints.json [--poses /path/to/clip_guide_poses.json]

Loads the constraints through Kimodo's own ``load_constraints_lst``, which runs
forward kinematics on the stored local rotations, and compares the resulting
joint positions against the positions Houdini recorded when the poses were
sampled.  A small error means the pose Kimodo will be constrained to is the
pose the animator actually keyed.

Exit code 0 if the error is under the tolerance, 1 otherwise.
"""

import argparse
import json
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("constraints", help="clip_constraints.json")
    parser.add_argument("--poses", default=None,
                        help="clip_guide_poses.json, for the position comparison")
    parser.add_argument("--tolerance", type=float, default=0.02,
                        help="max allowed joint position error in metres (default 0.02)")
    args = parser.parse_args(argv)

    import torch  # noqa: F401  (kimodo needs it loaded)
    from kimodo.constraints import load_constraints_lst
    from kimodo.skeleton import SOMASkeleton77

    skeleton = SOMASkeleton77()
    constraints = load_constraints_lst(args.constraints, skeleton)
    if not constraints:
        print("No constraints in %s" % args.constraints)
        return 1

    ok = True
    for c in constraints:
        frames = [int(f) for f in c.frame_indices.tolist()]
        print("%s: %d frames %s, %d joints" % (
            c.name, len(frames), frames, c.global_joints_positions.shape[-2]))

        if not args.poses:
            continue
        expected = json.loads(open(args.poses).read())
        by_frame = {f["kimodo_frame"]: f for f in expected["frames"]}
        for i, frame in enumerate(frames):
            source = by_frame.get(frame)
            if source is None or not source.get("positions"):
                continue
            got = c.global_joints_positions[i]
            want = torch.tensor(source["positions"], dtype=got.dtype)
            err = (got - want).norm(dim=-1)
            worst = float(err.max())
            print("  frame %-4d (houdini %-4d)  mean %.4f m  max %.4f m%s" % (
                frame, source["houdini_frame"], float(err.mean()), worst,
                "" if worst <= args.tolerance else "   <-- over tolerance"))
            ok = ok and worst <= args.tolerance

    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
