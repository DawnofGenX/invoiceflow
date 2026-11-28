#!/usr/bin/env python3
"""Generate one narration mp3 per demo scene from scripts/demo_narration.txt.

The narration script is a plain text file of [scene] sections. Each section is
synthesised with Edge TTS into <out>/<scene>.mp3, and the duration of every
clip is written next to it so the video builder can pad each scene to fit.

Note on the binary: use the edge-tts from the Hermes environment venv
(7.3.x). The older copy under ~/.hermes/hermes-agent/venv (7.2.7) fails with
WSServerHandshakeError 403 because its Sec-MS-GEC token scheme is stale.

Usage:
    /home/hermes/.hermes/installs/019d0d114d22b7e6/environments/2a7750add83b4eb4b8e6dedd093666cc/venv/bin/python \
        scripts/make_narration.py --script scripts/demo_narration.txt --out /tmp/nar
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

EDGE_TTS = (
    "/home/hermes/.hermes/installs/019d0d114d22b7e6/environments/"
    "2a7750add83b4eb4b8e6dedd093666cc/venv/bin/edge-tts"
)
FFPROBE = "ffprobe"


def parse_script(path: Path) -> dict[str, str]:
    sections: dict[str, str] = {}
    cur: str | None = None
    buf: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = re.match(r"^\[(\w+)\]\s*(\d+ words)?\s*$", line.strip())
        if m:
            if cur:
                sections[cur] = "\n".join(buf).strip()
            cur = m.group(1)
            buf = []
        elif cur is not None:
            buf.append(line)
    if cur:
        sections[cur] = "\n".join(buf).strip()
    return {k: v for k, v in sections.items() if v}


def duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return round(float(out.stdout.strip()), 3)


async def synth(scene: str, text: str, out: Path, voice: str, rate: str) -> None:
    target = out / f"{scene}.mp3"
    cmd = [
        EDGE_TTS,
        "--voice", voice,
        f"--rate={rate}",
        "--text", text,
        "--write-media", str(target),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"edge-tts failed for {scene}: {err.decode()[-400:]}")


async def main_async(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sections = parse_script(Path(args.script).resolve())

    manifest: dict[str, dict] = {}
    for scene, text in sections.items():
        await synth(scene, text, out, args.voice, args.rate)
        dur = duration(out / f"{scene}.mp3")
        words = len(text.split())
        wpm = round(words / (dur / 60)) if dur else 0
        manifest[scene] = {
            "file": str(out / f"{scene}.mp3"),
            "seconds": dur,
            "words": words,
            "wpm": wpm,
            "text": text,
        }
        print(f"{scene:<14} {dur:6.2f}s  {words:3d}w  {wpm:3d}wpm")

    (out / "narration.json").write_text(json.dumps(manifest, indent=2))
    total = sum(m["seconds"] for m in manifest.values())
    print(f"\ntotal narration: {total:.1f}s ({round(total / 60, 2)} min)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="/home/hermes/invoiceflow/scripts/demo_narration.txt")
    ap.add_argument("--out", default="/home/hermes/.hermes/cache/scratch/demo_take/nar")
    ap.add_argument("--voice", default="en-GB-SoniaNeural")
    ap.add_argument("--rate", default="-8%")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
