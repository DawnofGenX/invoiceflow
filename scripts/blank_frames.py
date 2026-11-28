#!/usr/bin/env python3
"""Report blank/near-blank frames in a video.

A demo frame is "blank" when it carries almost no ink: the product renders
dark text on a pale ground, so a frame whose pixels are nearly all at the
background level has nothing for a judge to read.

The metric: fraction of pixels whose luminance is more than 60 levels below
the frame's own median. A rendered page scores high; an empty canvas scores
near zero.

Usage:
    python3 scripts/blank_frames.py <file> [--fps 25] [--ink-threshold 0.004]
"""
from __future__ import annotations

import argparse
import subprocess

import numpy as np

W, H = 320, 180


def ink_fraction(buf: bytes) -> float:
    a = np.frombuffer(buf, dtype=np.uint8).reshape(H, W).astype(np.int16)
    med = np.median(a)
    return float((med - a > 60).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--ink-threshold", type=float, default=0.004)
    args = ap.parse_args()

    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", args.path, "-vf", f"scale={W}:{H}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    size = W * H
    n = len(out) // size
    blank_runs: list[tuple[float, float]] = []
    run_start: float | None = None
    for i in range(n):
        frac = ink_fraction(out[i * size:(i + 1) * size])
        if frac < args.ink_threshold:
            if run_start is None:
                run_start = i / args.fps
        else:
            if run_start is not None:
                blank_runs.append((run_start, i / args.fps))
                run_start = None
    if run_start is not None:
        blank_runs.append((run_start, n / args.fps))

    print(f"{args.path}: {n} frames @ {args.fps}fps, "
          f"ink threshold {args.ink_threshold}")
    if not blank_runs:
        print("  no blank frames")
        return 0
    total = 0.0
    for start, end in blank_runs:
        dur = end - start
        total += dur
        print(f"  BLANK {start:7.2f}s -> {end:7.2f}s  ({dur:.2f}s)")
    print(f"  total blank: {total:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
