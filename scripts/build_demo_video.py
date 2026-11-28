#!/usr/bin/env python3
"""Assemble the InvoiceFlow demo video from recorded scenes, cards and narration.

Inputs
    <take>/scene_<name>.webm        one recording per scene (from record_demo.py)
    <take>/cards/card_<name>.png    title / problem / architecture / outro cards
    <take>/nar/<name>.mp3           narration per scene (from make_narration.py)

Output
    <out>/invoiceflow_demo.mp4      1920x1080, H.264 yuv420p, 25 fps, with audio

Rules
  * A scene is never cut mid-sentence: if the narration is longer than the
    recording, the last frame is held (tpad clone) for the difference. If the
    recording is longer, the narration is padded with silence.
  * Every segment gets a 0.3s fade in and out so the cuts are not harsh.
  * The video is H.264 + AAC in yuv420p, which is what Devpost accepts.

Usage:
    python3 scripts/build_demo_video.py --take <take_dir> --out <out_dir>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dead_air import leading_dead_air  # noqa: E402  (local module, needs the path above)

FPS = 25
FADE = 0.3
BG = "0xf2f2ea"

# The running order of the demo: the argument, then the proof.
PLAN = [
    {"kind": "card", "name": "title", "narration": "title"},
    {"kind": "card", "name": "problem", "narration": "problem"},
    {"kind": "scene", "name": "register", "narration": "register"},
    {"kind": "scene", "name": "settle", "narration": "settle"},
    {"kind": "scene", "name": "record", "narration": "record"},
    {"kind": "scene", "name": "duplicate", "narration": "duplicate"},
    {"kind": "scene", "name": "hold", "narration": "hold"},
    {"kind": "scene", "name": "held", "narration": "held"},
    {"kind": "scene", "name": "evidence", "narration": "evidence"},
    {"kind": "card", "name": "architecture", "narration": "architecture"},
    {"kind": "card", "name": "outro", "narration": "outro"},
]


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + proc.stderr[-4000:])


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", default="/home/hermes/.hermes/cache/scratch/demo_take")
    ap.add_argument("--out", default="/home/hermes/.hermes/cache/scratch/demo_take/out")
    args = ap.parse_args()

    take = Path(args.take).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    nar_dir = take / "nar"

    # ---- plan the segments -------------------------------------------------
    segments = []
    for item in PLAN:
        if item["kind"] == "card":
            src = take / "cards" / f"card_{item['name']}.png"
            base = None
        else:
            src = take / f"scene_{item['name']}.webm"
            base = probe_duration(src) if src.exists() else None
        if not src.exists():
            print(f"SKIP {item['name']}: {src} missing", file=sys.stderr)
            continue

        # A Playwright recording starts before the page's first paint, so every
        # scene opens with dead air. Measure it and cut it, otherwise the demo
        # opens on a blank canvas.
        trim = 0
        if item["kind"] == "scene":
            trim, _ = leading_dead_air(str(src))
            trim_s = trim / 25.0

        nar_file = nar_dir / f"{item['narration']}.mp3"
        nar_dur = probe_duration(nar_file) if nar_file.exists() else 0.0

        if base is None:                      # a card: its length comes from the narration
            dur = nar_dur + 0.9 if nar_dur else 5.0
            hold = 0.0
        else:
            base -= trim_s                    # the dead air is cut from the head
            dur = max(base, nar_dur + 0.8 if nar_dur else 0.0)
            hold = max(dur - base, 0.0)
        segments.append({
            "kind": item["kind"], "name": item["name"], "src": str(src),
            "narration_file": str(nar_file) if nar_file.exists() else None,
            "hold": hold, "dur": dur, "base": base, "nar_dur": nar_dur,
            "trim_frames": trim,
        })

    if not segments:
        print("nothing to build", file=sys.stderr)
        return 2

    # ---- build the ffmpeg graph --------------------------------------------
    args_in: list[str] = []
    parts: list[str] = []
    in_idx = 0  # ffmpeg input counter: every segment consumes 2 inputs
    for i, seg in enumerate(segments):
        if seg["kind"] == "card":
            args_in += ["-loop", "1", "-t", f"{seg['dur']:.3f}", "-i", seg["src"]]
        else:
            args_in += ["-i", seg["src"]]
        v_idx = in_idx
        in_idx += 1
        # the narration input goes right after the video input
        if seg["narration_file"]:
            args_in += ["-i", seg["narration_file"]]
            a_idx = in_idx
            in_idx += 1
        else:
            a_idx = None

        dur = seg["dur"]
        v = f"[{v_idx}:v]"
        if seg.get("trim_frames"):
            # trim keeps the original timestamps, so the segment would start at
            # PTS 1.16s and leave a 1.16s hole in the concat. setpts re-bases it.
            v += (f"trim=start_frame={seg['trim_frames']},"
                  f"setpts=PTS-STARTPTS,")
        v += (
            f"scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color={BG},"
            f"setsar=1,fps={FPS},format=yuv420p"
        )
        if seg["hold"] > 0:
            v += f",tpad=stop_mode=clone:stop_duration={seg['hold']:.3f}"
        v += (
            f",fade=t=in:st=0:d={FADE},"
            f"fade=t=out:st={max(dur - FADE, 0):.3f}:d={FADE}[v{i}]"
        )
        parts.append(v)

        if a_idx is not None:
            parts.append(
                f"[{a_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"apad=pad_dur={dur:.3f},atrim=duration={dur:.3f},"
                f"afade=t=in:st=0:d=0.2,afade=t=out:st={max(dur - 0.3, 0):.3f}:d=0.3[a{i}]"
            )
        else:
            parts.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000,"
                f"atrim=duration={dur:.3f}[a{i}]"
            )

    concat = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
    filter_complex = ";".join(parts) + ";" + f"{concat}concat=n={len(segments)}:v=1:a=1[outv][outa]"

    target = out / "invoiceflow_demo.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    cmd += args_in
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(target),
    ]
    print(f"building {target} from {len(segments)} segments")
    run(cmd)

    dur = probe_duration(target)
    size = target.stat().st_size
    print(f"\n{target}")
    print(f"  duration {dur:.2f}s ({round(dur / 60, 2)} min)")
    print(f"  size     {size / 1_048_576:.1f} MB")
    for seg in segments:
        print(f"  {seg['kind']:<5} {seg['name']:<13} {seg['dur']:6.2f}s  "
              f"(video {seg['base'] if seg['base'] else 'card'}, narration {seg['nar_dur']:.2f}s"
              + (f", trimmed {seg['trim_frames']} dead-air frames" if seg.get("trim_frames") else "")
              + ")")
    (out / "build_manifest.json").write_text(json.dumps(
        {"target": str(target), "duration": dur, "size": size, "segments": segments}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())