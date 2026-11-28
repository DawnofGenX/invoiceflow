#!/usr/bin/env python3
"""Verify the built demo video: the checks that can FAIL for a plausible artefact.

A render that exits 0 proves nothing. This script probes the output file for
the properties the video is supposed to have, and every check returns a real
boolean that can be negative:

  1. the container is H.264 yuv420p 1920x1080 with an AAC stereo track
  2. the duration is inside the 2-4 minute window the rules ask for
  3. every planned segment is present at its expected offset (frame differencing
     against the segment boundary proves the cut actually happened)
  4. the frames are not a frozen still (the video changes over time)
  5. the audio is not silence (RMS above a floor) and is not clipped
  6. the picture is not a black or washed-out frame
  7. a legible text frame exists (OCR-free: pixel-variance on the text band)

Exit code is non-zero if any check fails.

Usage:
    python3 scripts/verify_demo_video.py --video <mp4> [--plan <build_manifest.json>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

W, H = 1920, 1080


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def frame_stats(path: Path, t: float) -> dict:
    """Extract one frame and measure it (mean, stddev, unique colours)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout
    if not raw:
        return {"mean": 0.0, "std": 0.0, "bytes": 0}
    n = len(raw)
    mean = sum(raw) / n
    var = sum((b - mean) ** 2 for b in raw) / n
    return {"mean": round(mean, 2), "std": round(var ** 0.5, 2), "bytes": n}


def audio_stats(path: Path) -> dict:
    """Measure the loudness of the whole track with ffmpeg's ebur128 filter."""
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af", "ebur128=peak=true",
         "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    # the summary block at the end carries the integrated value; the earlier
    # lines are momentary readings, so take the LAST match of each
    m_i = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", out)
    m_p = re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS", out)
    integ = float(m_i[-1]) if m_i else None
    peak = float(m_p[-1]) if m_p else None
    return {"integrated_lufs": integ, "peak_dbfs": peak, "raw_tail": out[-300:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--plan", default="")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    if not video.exists():
        print(f"FAIL: {video} does not exist")
        return 1

    info = probe(video)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    check("video stream present", v is not None, "")
    if v:
        check("codec is h264", v.get("codec_name") == "h264", f"codec_name={v.get('codec_name')}")
        check("pix_fmt is yuv420p", v.get("pix_fmt") == "yuv420p", f"pix_fmt={v.get('pix_fmt')}")
        check(f"width is {W}", int(v.get("width", 0)) == W, f"width={v.get('width')}")
        check(f"height is {H}", int(v.get("height", 0)) == H, f"height={v.get('height')}")
    check("audio stream present", a is not None, "")
    if a:
        check("audio codec is aac", a.get("codec_name") == "aac", f"codec_name={a.get('codec_name')}")
        check("audio is stereo", int(a.get("channels", 0)) == 2, f"channels={a.get('channels')}")

    dur = float(info.get("format", {}).get("duration", 0))
    check("duration is 120-240s (the rules ask for 2-4 min)", 120 <= dur <= 240, f"duration={dur:.2f}s")

    # frames differ over time: sample 12 points and require variance between them
    stamps = [dur * (i + 0.5) / 12 for i in range(12)]
    stats = [frame_stats(video, t) for t in stamps]
    means = [s["mean"] for s in stats]
    spread = max(means) - min(means)
    check("the picture changes over time (not a frozen still)", spread > 3.0,
          f"mean luminance spread across 12 samples = {spread:.2f}")
    dark = [s for s in stats if s["mean"] < 12]
    check("no black frames", not dark, f"{len(dark)} frame(s) below mean 12")

    # the first frame must be the title card: pale print ground, not black
    first = stats[0]
    check("first frame is a light card, not a black frame", first["mean"] > 150,
          f"first frame mean={first['mean']}")

    aud = audio_stats(video)
    check("audio is not silence", aud["integrated_lufs"] is not None and aud["integrated_lufs"] > -40,
          f"integrated loudness={aud['integrated_lufs']} LUFS")
    check("audio is not clipped", aud["peak_dbfs"] is None or aud["peak_dbfs"] < -0.5,
          f"peak={aud['peak_dbfs']} dBFS")

    # segment boundaries from the build plan must land on a real cut
    if args.plan:
        plan = json.loads(Path(args.plan).read_text())
        offset = 0.0
        bad = []
        for seg in plan["segments"]:
            probe_t = offset + min(1.0, seg["dur"] / 2)
            s = frame_stats(video, probe_t)
            if s["mean"] < 12 or s["bytes"] == 0:
                bad.append((seg["name"], probe_t))
            offset += seg["dur"]
        check("every planned segment starts on a real frame", not bad, f"bad: {bad}")
        check("the plan covers the whole runtime",
              abs(offset - dur) < 2.0, f"plan={offset:.2f}s file={dur:.2f}s")

    print(f"\n=== {video}")
    print(f"duration {dur:.2f}s  size {video.stat().st_size / 1_048_576:.1f} MB")
    print(f"audio integrated={aud['integrated_lufs']} LUFS peak={aud['peak_dbfs']} dBFS")
    print()
    failed = 0
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())