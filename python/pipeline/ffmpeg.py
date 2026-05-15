"""
ffmpeg wrappers for encoding image sequences to MP4.
"""

import logging
import subprocess

from .config import load_config

logger = logging.getLogger("pipeline")


def build_ffmpeg_cmd(image_seq_path: str, output_mp4: str, fps: int = None) -> list[str]:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    return [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-i", image_seq_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        output_mp4,
    ]


def encode_mp4(jpg_seq_path: str, output_mp4: str, fps: int = None,
               frame_start: int = 1) -> None:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    ffmpeg_input = jpg_seq_path.replace("$F4", "%04d")
    cmd = [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-start_number", str(frame_start),
        "-i", ffmpeg_input,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-y",
        output_mp4,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (code {result.returncode}):\n"
            + result.stderr.decode(errors="replace")
        )
    logger.info("Encoded: %s", output_mp4)


def encode_mp4_from_exr(exr_seq_path: str, output_mp4: str, fps: int = None,
                         frame_start: int = 1) -> None:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    ffmpeg_input = exr_seq_path.replace("$F4", "%04d")
    cmd = [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-start_number", str(frame_start),
        "-i", ffmpeg_input,
        "-vf", "tonemap=reinhard:desat=0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-y",
        output_mp4,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (code {result.returncode}):\n"
            + result.stderr.decode(errors="replace")
        )
    logger.info("Encoded from EXR: %s", output_mp4)
