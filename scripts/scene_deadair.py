#!/usr/bin/env python3
"""Find dead air at the edges of a recorded scene.

A screen recording often opens (or ends) with a blank/loading frame — the
page has painted nothing yet. That dead air lands in the final video and
reads as a stalled demo to a judge.

This tool decodes a scene file to tiny grayscale frames and reports the
leading and trailing run of frames that are visually identical to the
first/last frame. Identical bytes => the picture did not change.

Usage:
    python3 scripts/scene_deadair.py <scene.webm> [<scene.webm> ...]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

W, H = 32, 18
FPS = 25


def frames(path: Path) -> list[bytes]:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={W}:{H}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    size = W * H
    return [out[i:i + size] for i in range(0, len(out) - size + 1, size)]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for arg in sys.argv[1:]:
        path = Path(arg)
        fr = frames(path)
        if not fr:
            print(f"{path.name}: no frames decoded")
            continue
        lead = 0
        for f in fr[1:]:
            if f == fr[0]:
                lead += 1
            else:
                break
        tail = 0
        for f in reversed(fr[:-1]):
            if f == fr[-1]:
                tail += 1
            else:
                break
        print(f"{path.name}: {len(fr)} frames  leading-identical={lead} "
              f"({lead / FPS:.2f}s)  trailing-identical={tail} ({tail / FPS:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
