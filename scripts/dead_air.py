#!/usr/bin/env python3
"""Measure the dead air at the start of a screen recording.

A Playwright video starts capturing the moment the browser context is
created, so the first frames are the page's pre-first-paint state: a blank
canvas with no app content. In the finished demo video that reads as a
stalled screen, so it has to be measured and trimmed.

A frame is "low content" when it carries almost no structure: the share of
pixels whose luminance changes sharply against a neighbour (an edge) is far
below the scene's own baseline. A rendered page with text and rules scores
an order of magnitude higher than an empty canvas.

Both a command line (report) and a library entry point (`leading_dead_air`)
are provided; the builder uses the latter to trim each scene.

Usage:
    python3 scripts/dead_air.py <file> [<file> ...]
"""
from __future__ import annotations

import statistics
import subprocess
import sys

import numpy as np

W, H = 480, 270
LOW_CONTENT_RATIO = 0.25   # a frame is low-content below this share of the baseline


def edge_scores(path: str, w: int = W, h: int = H) -> list[float]:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    size = w * h
    n = len(out) // size
    scores: list[float] = []
    for i in range(n):
        a = np.frombuffer(out[i * size:(i + 1) * size], dtype=np.uint8)
        a = a.reshape(h, w).astype(np.int16)
        gy = np.abs(np.diff(a, axis=0))
        gx = np.abs(np.diff(a, axis=1))
        scores.append(float(((gy > 25).sum() + (gx > 25).sum()) / (h * w)))
    return scores


def leading_dead_air(path: str, fps: float = 25.0) -> tuple[int, float]:
    """Return (frames to trim from the head, baseline edge score).

    The baseline is the median edge score of the second half of the clip —
    the steady state once the page has rendered. Leading frames scoring
    below LOW_CONTENT_RATIO of the baseline are pre-paint dead air.
    """
    scores = edge_scores(path)
    if len(scores) < 10:
        return 0, 0.0
    baseline = statistics.median(scores[len(scores) // 2:])
    if baseline <= 0:
        return 0, baseline
    trim = 0
    for s in scores:
        if s < baseline * LOW_CONTENT_RATIO:
            trim += 1
        else:
            break
    # never trim the whole clip
    trim = min(trim, max(0, len(scores) - 5))
    return trim, baseline


def report(path: str) -> None:
    scores = edge_scores(path)
    if not scores:
        print(f"{path}: no frames")
        return
    baseline = statistics.median(scores[len(scores) // 2:])
    low = [v < baseline * LOW_CONTENT_RATIO for v in scores]
    lead = 0
    for b in low:
        if b:
            lead += 1
        else:
            break
    trail = 0
    for b in reversed(low):
        if b:
            trail += 1
        else:
            break
    print(f"{path}: {len(scores)} frames  baseline={baseline:.4f}  "
          f"leading_low_content={lead} ({lead / 25:.2f}s)  "
          f"trailing_low_content={trail} ({trail / 25:.2f}s)  "
          f"total_low_content={sum(low)} ({sum(low) / 25:.2f}s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    for p in sys.argv[1:]:
        report(p)
