#!/usr/bin/env python3
"""Record the InvoiceFlow demo as a sequence of scene videos.

Each scene is a separate Playwright context so that a single broken scene can be
re-recorded without redoing the whole take. The script drives the LIVE public
deployment (or any --base-url), captures the agent stream as it streams, and
writes:

    <out>/scene_<NN>_<name>.webm     one video per scene
    <out>/manifest.json               scene name -> video path, actions, notes
    <out>/shots/<scene>.png           a still from the end of each scene

The narration is produced separately (one mp3 per scene) and muxed in by
scripts/build_demo_video.py, so the take and the voice-over can be iterated
independently.

Requires a Python interpreter that has Playwright installed. On this machine
that is /usr/bin/python3 (Playwright 1.61), not the default python3.

Usage:
    /usr/bin/python3 scripts/record_demo.py \
        --base-url https://hermes-vm.tailfd1655.ts.net \
        --out /home/hermes/.hermes/cache/scratch/demo_take \
        --samples backend/demo-data/sample_invoices \
        --scenario full
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright

VIEW_W, VIEW_H = 1920, 1080

CURSOR_JS = """
(() => {
  if (window.__ifCursorReady) return;
  // document-start runs before <body> exists; without this guard the append
  // throws, window.__ifCursor stays set, and every later injection
  // short-circuits -> the demo records with no visible pointer at all.
  if (!document.body) return;
  if (window.__ifCursor) { window.__ifCursorReady = true; return; }
  window.__ifCursor = true;
  window.__ifCursorReady = true;
  const dot = document.createElement('div');
  dot.id = '__if_cursor_dot';
  dot.style.cssText = 'position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;'
    + 'border-radius:50%;background:#b4481f;border:2px solid #f2f2ea;z-index:2147483647;'
    + 'pointer-events:none;box-shadow:0 0 0 1px rgba(0,0,0,.35);transition:transform .08s ease-out;';
  document.body.appendChild(dot);
  const ring = document.createElement('div');
  ring.id = '__if_cursor_ring';
  ring.style.cssText = 'position:fixed;left:0;top:0;width:34px;height:34px;margin:-17px 0 0 -17px;'
    + 'border-radius:50%;border:2px solid #b4481f;z-index:2147483646;pointer-events:none;opacity:0;'
    + 'transition:opacity .25s ease-out, transform .18s ease-out;';
  document.body.appendChild(ring);
  document.addEventListener('mousemove', (e) => {
    // Under a root CSS zoom the mouse coordinates arrive in zoomed space but a
    // position:fixed child is scaled again by the zoom -> the dot lands at
    // zoom*zoom. Divide it back out so the dot sits on the pointer.
    const z = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
    const x = e.clientX / z;
    const y = e.clientY / z;
    dot.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    ring.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(1)';
    ring.style.opacity = '0.45';
    clearTimeout(window.__ifRingT);
    window.__ifRingT = setTimeout(() => { ring.style.opacity = '0'; }, 500);
  }, true);
  document.addEventListener('mousedown', () => {
    dot.style.transform += ' scale(0.6)';
    setTimeout(() => { dot.style.transform = dot.style.transform.replace(' scale(0.6)', ''); }, 160);
  }, true);
})();
"""

# The capture size and the viewport MUST match: if the viewport is smaller than
# record_video_size, Playwright pads the recording with a grey gutter, and the
# demo shows the app floating in a dead border.
VIEW_W, VIEW_H = 1920, 1080
WIDTH, HEIGHT = 1920, 1080

# The camera. A 1920x1080 frame renders the product at its true 12px CSS type,
# which is unreadable on video. Pushing the page in (CSS zoom) and centring the
# block we want to show makes the reasoning legible without touching the
# product.
#
# Two hard constraints, both measured:
#   1. The zoom is capped at CAMERA_MAX_ZOOM. Root zoom shrinks the LAYOUT
#      viewport to 1920/zoom CSS px, so a zoom above 1.875 drops the page
#      below Tailwind's `lg` breakpoint (1024px) and the two-column layout
#      collapses — the app ends up in a narrow column with dead space beside
#      it. At 1.8 the layout is intact and the reasoning renders at 21.6px.
#   2. The framed block is placed BELOW the sticky navbar, never under it: at
#      zoom 1.8 the nav is ~103 device px tall and the first log row was
#      sliding underneath it, sliced in half.
CAMERA_MAX_ZOOM = 1.85
CAMERA_MIN_ZOOM = 1.0
CAMERA_FIT_MARGIN = 24  # px of breathing room around the framed block
CAMERA_HEADER_GAP = 16  # px between the sticky nav and the framed block

# The live-run panel: the section whose .micro label says "live run".
LIVE_RUN_FINDER = """
() => {
  const sec = [...document.querySelectorAll('section')].find(s =>
    (s.querySelector('.micro')?.textContent || '').toLowerCase().includes('live run'));
  return sec || null;
}
"""

# Explicit finders, one per thing the camera frames. Each was read off the
# real component source (frontend/components/*.tsx, frontend/app/*/page.tsx)
# so the camera frames the BLOCK that carries the payload, not its heading.
#
# 1. The decision lines on the invoice record page: the <h2> says "Decision
#    lines" and the lines live in the <ol> inside the same <section>.
RECORD_LINES_FINDER = """
() => {
  const h = [...document.querySelectorAll('h2')].find(e =>
    (e.innerText || '').toLowerCase().includes('decision lines'));
  return h ? (h.closest('section') || h.parentElement) : null;
}
"""

# 2. The held invoice on the approvals page: the caption "Reason for hold"
#    sits inside the <li> card that carries vendor, amount and the buttons.
HELD_CARD_FINDER = """
() => {
  const p = [...document.querySelectorAll('p')].find(e =>
    (e.innerText || '').trim().toLowerCase().includes('reason for hold'));
  return p ? (p.closest('li') || p.parentElement) : null;
}
"""

# 3. The KPI strip on the evidence page: five cells (decisions, per invoice,
#    automation, confidence, low confidence) in one bordered row.
AUDIT_KPI_FINDER = """
() => {
  const p = [...document.querySelectorAll('p')].find(e =>
    (e.innerText || '').trim().toLowerCase() === 'decisions');
  return p ? (p.closest('.grid') || p.parentElement) : null;
}
"""

# 4. The recent-decisions list on the evidence page: heading + the <ol> of
#    printed lines.
AUDIT_RECENT_FINDER = """
() => {
  const h = [...document.querySelectorAll('h2')].find(e =>
    (e.innerText || '').toLowerCase().includes('recent decisions'));
  return h ? (h.closest('section') || h.parentElement) : null;
}
"""

# 5. The rules-that-fired table on the evidence page.
AUDIT_RULES_FINDER = """
() => {
  const h = [...document.querySelectorAll('h2')].find(e =>
    (e.innerText || '').toLowerCase().includes('rules that fired'));
  return h ? (h.closest('section') || h.parentElement) : null;
}
"""

# Find a block by a visible label, then walk up to the smallest self-contained
# ancestor that still holds the label AND its payload (a heading's section, a
# caption's card) without swallowing the whole page.
#
# The rules that pick the block, in order:
#   1. the tightest element whose text contains the needle (the label itself)
#   2. climb while the ancestor is a LABEL (short text, mostly the label)
#   3. stop at the first ancestor that is a BLOCK (has a visible box) and
#      still holds the payload
# The final answer is that block.
#
# NOTE: no `//` comments in this string. It is concatenated into one line
# before eval, so a line comment swallows the closing braces and the whole
# finder dies with "SyntaxError: Unexpected end of input".
BLOCK_FINDER_TMPL = """
() => {
  const needle = %s.toLowerCase();
  const all = [...document.querySelectorAll('*')];
  const hits = all.filter(e => (e.innerText || '').toLowerCase().includes(needle));
  if (!hits.length) return null;
  hits.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
  const label = hits[0];
  const labelText = (label.innerText || '').trim();
  const labelLen = labelText.length;
  const pageText = (document.body.innerText || '').length;
  let el = label;
  let best = label;
  let depth = 0;
  while (el && el.tagName !== 'BODY' && depth < 7) {
    const txt = (el.innerText || '').trim();
    const rect = el.getBoundingClientRect();
    const isBox = rect.width > 140 && rect.height > 20;
    const isWholePage = txt.length >= pageText * 0.85;
    const isJustLabel = txt.length <= labelLen + 4;
    if (isBox && !isWholePage && !isJustLabel) {
      best = el;
      break;
    }
    el = el.parentElement;
    depth++;
  }
  return best;
}
"""

# Measure the target and pick the largest zoom (capped) at which it still
# fits the frame. Runs BEFORE the push so the camera never frames a block it
# cannot show.
#
# All the maths is in CSS px at zoom 1 and then scaled by the candidate zoom,
# because the frame is a fixed 1920x1080 device raster: root zoom does NOT
# change window.innerWidth/innerHeight (measured: still 1920x1080 at zoom
# 2.33), it scales the content inside it.
#
#   width:  cssW * z <= frameW - 2*margin
#   height: cssH * z <= frameH - margin - gap - navCss*z
# The nav height scales with the zoom too, and the framed block has to sit
# BELOW the sticky navbar, so it is subtracted from the available height.
#
# The zoom is also capped so the LAYOUT viewport (frameW / z) stays above
# Tailwind's `lg` breakpoint (1024px) plus a safety band — above that the
# two-column layout collapses into one narrow column with dead space beside
# it, which looks broken in the frame.
CAMERA_FIT_JS = """
([finderSrc, maxZoom, margin, gap]) => {
  const finder = eval(finderSrc);
  const el = finder();
  if (!el) return null;
  const z0 = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  const r = el.getBoundingClientRect();
  const frameW = window.innerWidth;
  const frameH = window.innerHeight;
  const w = Math.max(1, r.width / z0);
  const h = Math.max(1, r.height / z0);
  const nav = document.querySelector('header');
  const navCss = nav ? nav.getBoundingClientRect().height / z0 : 0;
  const fitW = (frameW - margin * 2) / w;
  const fitH = (frameH - margin - gap) / (h + navCss);
  const layoutCap = frameW / 1056;
  const cap = Math.min(maxZoom, layoutCap);
  const fit = Math.min(fitW, fitH, cap);
  const chosen = Math.max(1, Math.min(cap, fit));
  return {width: Math.round(w), height: Math.round(h),
          viewport: [frameW, frameH], navCss: Math.round(navCss),
          fitW: Math.round(fitW * 100) / 100,
          fitH: Math.round(fitH * 100) / 100,
          layoutCap: Math.round(layoutCap * 100) / 100,
          fit: Math.round(fit * 100) / 100,
          chosen: Math.round(chosen * 100) / 100,
          scrollable: el.scrollHeight > el.clientHeight + 4};
}
"""

# Measure the sticky navbar in CSS px (at zoom 1) so the fit maths knows how
# much of the frame the header eats. The navbar is <header className="sticky
# top-0 z-40 ..."> in frontend/components/Navbar.tsx:61.
CAMERA_NAV_JS = """
() => {
  const nav = document.querySelector('header');
  if (!nav) return 0;
  return nav.getBoundingClientRect().height;
}
"""

# Zoom the page in (animated, so it reads as a camera move rather than a jump)
# and place the target under the sticky navbar.
#
# Positioning is done in DEVICE px and converted back to CSS px for the
# scroll: getBoundingClientRect() reports post-zoom (device) coordinates, and
# one CSS px of scroll moves the content z device px in the frame, so the
# scroll delta is (device delta) / z.
#
# The block is placed BELOW the sticky nav: at zoom 1.8 the nav is ~96 device
# px tall and the first log row was sliding underneath it, sliced in half.
# The scroll is clamped to the document, and a final instant correction of a
# few px lands the block exactly on the target line (a smooth scroll can
# still be a few px out when it is measured).
CAMERA_PUSH_JS = """
async ([zoom, finderSrc, block, gap]) => {
  const root = document.documentElement;
  const from = parseFloat(getComputedStyle(root).zoom) || 1;
  const start = performance.now();
  const dur = 900;
  await new Promise(resolve => {
    const step = (t) => {
      const k = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - k, 3);
      root.style.zoom = String(from + (zoom - from) * eased);
      if (k < 1) requestAnimationFrame(step);
      else resolve();
    };
    requestAnimationFrame(step);
  });
  const z = parseFloat(getComputedStyle(root).zoom) || 1;
  const finder = eval(finderSrc);
  if (!finder()) return null;
  finder().scrollIntoView({block: 'start', behavior: 'smooth'});
  await new Promise(r => setTimeout(r, 700));
  const nav = document.querySelector('header');
  const navH = nav ? nav.getBoundingClientRect().height : 0;
  const desired = navH + gap;
  const r0 = finder().getBoundingClientRect();
  const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
  const target = Math.max(0, Math.min(window.scrollY + (r0.top - desired) / z, maxScroll));
  window.scrollTo({top: target, behavior: 'smooth'});
  await new Promise(r => setTimeout(r, 800));
  const r1 = finder().getBoundingClientRect();
  const resid = r1.top - desired;
  if (Math.abs(resid) > 1) {
    window.scrollBy({top: resid / z, behavior: 'instant'});
    await new Promise(r => setTimeout(r, 200));
  }
  const el = finder();
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {top: Math.round(r.top), bottom: Math.round(r.bottom),
          width: Math.round(r.width), height: Math.round(r.height),
          zoom: z, navH: Math.round(navH), desired: Math.round(desired),
          residual: Math.round(r.top - desired)};
}
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def settle(page: Page, ms: int = 900) -> None:
    """Let animations/transitions land so the recording is not a blur."""
    await page.wait_for_timeout(ms)


async def scroll_to(page: Page, selector: str | None = None, y: int = 0, ms: int = 900) -> None:
    """Scroll the page (or to a selector) slowly enough to read on video."""
    if selector:
        try:
            await page.locator(selector).first.scroll_into_view_if_needed(timeout=10000)
            await page.wait_for_timeout(ms)
            return
        except Exception:
            pass
    await page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'smooth'}})")
    await page.wait_for_timeout(ms)


async def scroll_steps(page: Page, ys: list[int], ms: int = 900) -> None:
    """Scroll through several positions, pausing at each — reads as a camera move."""
    for y in ys:
        await page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'smooth'}})")
        await page.wait_for_timeout(ms)


async def push_in(page: Page, block: str = "center",
                  zoom: float | None = None) -> dict | None:
    """Zoom the page in and centre the live-run panel.

    A 1920x1080 frame renders the product at its true 12px CSS type, which is
    legible in a native still but turns to mush the moment a judge scales the
    video down. Pushing the page in (root CSS zoom) and centring the panel
    makes the reasoning render at 12*zoom device px while the whole panel
    still fits the frame. Measured at zoom 1.8: reasoning at 21.6 device px,
    all 9 log lines plus the closing border inside 1920x1080.

    If zoom is None the camera measures the panel and picks the largest zoom
    (up to CAMERA_MAX_ZOOM) at which it still fits the frame.
    """
    return await _push(page, LIVE_RUN_FINDER, block, zoom)


async def push_in_on(page: Page, selector: str, block: str = "center",
                     zoom: float | None = None) -> dict | None:
    """Same camera move, but centred on an arbitrary element."""
    finder = ("() => { const el = document.querySelector(%s); return el || null; }"
              % json.dumps(selector))
    return await _push(page, finder, block, zoom)


async def push_in_to_text(page: Page, needle: str, block: str = "center",
                          zoom: float | None = None) -> dict | None:
    """Same camera move, centred on the block labelled by `needle`.

    "Decision lines", "Reason for hold", "Decisions" — framed by their visible
    label instead of a brittle CSS selector.
    """
    finder = BLOCK_FINDER_TMPL % json.dumps(needle)
    return await _push(page, finder, block, zoom)


async def push_in_finder(page: Page, finder: str, block: str = "center",
                         zoom: float | None = None) -> dict | None:
    """Camera move onto a block located by an explicit finder function."""
    return await _push(page, finder, block, zoom)


async def _push(page: Page, finder: str, block: str, zoom: float | None) -> dict | None:
    """Measure, choose a zoom that fits, then push the camera in.

    The camera must never kill a scene: any failure is logged and the scene
    continues with whatever framing the page already has.
    """
    chosen = zoom
    fit_info = None
    if chosen is None:
        try:
            fit_info = await page.evaluate(
                CAMERA_FIT_JS,
                [finder, CAMERA_MAX_ZOOM, CAMERA_FIT_MARGIN, CAMERA_HEADER_GAP],
            )
        except Exception as exc:  # noqa: BLE001
            log(f"camera fit failed: {type(exc).__name__}: {exc}")
        if fit_info:
            chosen = fit_info["chosen"]
    if chosen is None:
        chosen = CAMERA_MAX_ZOOM
    try:
        out = await page.evaluate(CAMERA_PUSH_JS,
                                  [chosen, finder, block, CAMERA_HEADER_GAP])
    except Exception as exc:  # noqa: BLE001 - the camera must never kill a scene
        log(f"camera push failed: {type(exc).__name__}: {exc}")
        return None
    if out is None:
        log("camera push found no target")
        return None
    if fit_info:
        out["fit"] = fit_info
    out["requested_zoom"] = round(chosen, 2)
    log(f"camera: zoom={out.get('zoom')} target={out['width']}x{out['height']} "
        f"at y={out['top']}..{out['bottom']} nav={out.get('navH')} "
        f"resid={out.get('residual')}")
    return out


async def shot(page: Page, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(out / f"{name}.png"))


async def inject_cursor(page: Page) -> None:
    await page.add_init_script(CURSOR_JS)


async def goto(page: Page, base: str, path: str) -> None:
    await page.goto(f"{base}{path}", wait_until="domcontentloaded", timeout=60000)
    await page.evaluate(CURSOR_JS)
    await settle(page, 1500)


async def human_click(page: Page, locator, ms: int = 900) -> None:
    """Move the pointer onto the target, then click — so the video reads as a hand."""
    box = await locator.bounding_box()
    if box:
        steps = 18
        start = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
        await page.mouse.move(start["x"] - 180, start["y"] - 120, steps=6)
        await page.wait_for_timeout(220)
        await page.mouse.move(start["x"], start["y"], steps=steps)
        await page.wait_for_timeout(320)
    await locator.click()
    await page.wait_for_timeout(ms)


async def wait_stream_complete(page: Page, timeout_s: int = 180) -> list[str]:
    """Wait for the agent stream to report completion, then return its lines."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            state = await page.evaluate(
                """() => {
                    const sec = [...document.querySelectorAll('section')].find(s =>
                        (s.querySelector('.micro')?.textContent || '').includes('Live run'));
                    if (!sec) return null;
                    const status = sec.querySelector('span.micro')?.parentElement?.parentElement?.innerText || '';
                    const lines = [...sec.querySelectorAll('ol li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim());
                    return { done: /complete/i.test(status), lines };
                }"""
            )
        except Exception:
            state = None
        if state and state.get("done"):
            await settle(page, 1200)
            return state.get("lines", [])
        await page.wait_for_timeout(700)
    raise TimeoutError("agent stream did not complete in time")


async def read_record_audit(page: Page) -> list[str]:
    """Pull the printed decision lines off the invoice record page."""
    try:
        await page.wait_for_selector("text=/po_match|duplicate|new_vendor|not_an_invoice|rule/i", timeout=30000)
    except Exception:
        pass
    await settle(page, 1500)
    return await page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('li, tr, div').forEach(el => {
                const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                if (!t || t.length > 320) return;
                if (/(po_match|duplicate_detected|new_vendor_verification|not_an_invoice|validation_failed|auto_approv)/.test(t)) {
                    if (!out.includes(t)) out.push(t);
                }
            });
            return out.slice(0, 24);
        }"""
    )


async def reset_live_harness_artifacts(base: str) -> dict:
    """Clear the demo's own harness rows before a take.

    The duplicate detector is content-based: if a previous take left the same
    fixture in the DB, the next upload of that fixture is (correctly) flagged as
    a duplicate and the "settle" scene would show REVIEW instead of SETTLED.
    The reset endpoint is disabled unless E2E_RESET_TOKEN is set, in which case
    this is a no-op and the take must be run against a clean database.
    """
    token = os.environ.get("INVOICEFLOW_E2E_RESET_TOKEN", "").strip()
    if not token:
        return {"reset": False, "reason": "no INVOICEFLOW_E2E_RESET_TOKEN set"}
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/maintenance/reset-e2e",
        headers={"X-E2E-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"reset": True, "body": resp.read().decode()}
    except urllib.error.HTTPError as exc:
        return {"reset": False, "reason": f"HTTP {exc.code}: {exc.read().decode()[:200]}"}
    except Exception as exc:  # noqa: BLE001
        return {"reset": False, "reason": repr(exc)}


class SceneRunner:
    def __init__(self, browser, out: Path, base: str, samples: Path, headless: bool):
        self.browser = browser
        self.out = out
        self.base = base
        self.samples = samples
        self.headless = headless
        self.manifest: list[dict] = []
        self.state: dict = {}

    async def run(self, name: str, fn, keep_video: bool = True) -> dict:
        log(f"scene {name}: start")
        t0 = time.time()
        ctx = await self.browser.new_context(
            viewport={"width": VIEW_W, "height": VIEW_H},
            record_video_dir=str(self.out),
            record_video_size={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
            locale="en-US",
        )
        page = await ctx.new_page()
        await inject_cursor(page)
        notes: dict = {}
        try:
            notes = await fn(self, page) or {}
        finally:
            await ctx.close()  # finalises the video file
        # Playwright names videos page@<uuid>.webm in the dir
        vids = sorted(self.out.glob("page@*.webm"), key=lambda p: p.stat().st_mtime)
        target = self.out / f"scene_{name}.webm"
        if vids:
            shutil.move(str(vids[-1]), str(target))
        dur = time.time() - t0
        entry = {
            "name": name,
            "video": str(target) if target.exists() else None,
            "seconds": round(dur, 2),
            "notes": notes,
        }
        self.manifest.append(entry)
        log(f"scene {name}: done in {dur:.1f}s")
        return entry


# --------------------------------------------------------------------------- scenes


async def scene_register(runner: SceneRunner, page: Page) -> dict:
    """The register: every invoice, its disposition, its confidence."""
    await goto(page, runner.base, "/")
    await scroll_steps(page, [0, 260, 520, 380], ms=1100)
    await settle(page, 1600)
    await shot(page, runner.out / "shots", "register")
    body = await page.inner_text("body")
    return {"title": await page.title(), "amounts_seen": re.findall(r"\$[\d,]+(?:\.\d\d)?", body)[:8]}


async def scene_settle(runner: SceneRunner, page: Page) -> dict:
    """Upload a clean invoice and watch the four agents reason out loud."""
    await goto(page, runner.base, "/upload")
    sample = runner.samples / "sample-clean.pdf"
    await page.set_input_files("input[type=file]", str(sample))
    await settle(page, 800)
    await shot(page, runner.out / "shots", "settle_staged")
    btn = page.locator("button", has_text=re.compile(r"Process .*invoice", re.I))
    await human_click(page, btn.first, ms=1200)
    lines = await wait_stream_complete(page)
    await settle(page, 1800)
    # Push the camera in so the reasoning is readable at video scale, then
    # hold on the panel while the narration talks about it.
    framing = await push_in(page)
    await settle(page, 1600)
    await shot(page, runner.out / "shots", "settle_stream")
    link = page.locator("a", has_text=re.compile(r"open record", re.I)).first
    href = await link.get_attribute("href")
    runner.state["last_invoice_path"] = href
    return {"sample": sample.name, "stream_lines": lines, "record_path": href,
            "framing": framing}


async def scene_record(runner: SceneRunner, page: Page) -> dict:
    """The record the pipeline wrote: rule, confidence, timing, sentence."""
    path = runner.state.get("last_invoice_path")
    if not path:
        raise RuntimeError("scene_record needs scene_settle to run first")
    await goto(page, runner.base, path)
    await settle(page, 1500)
    audit = await read_record_audit(page)
    # Frame the printed decision lines: those are the claim of the product.
    framing = await push_in_finder(page, RECORD_LINES_FINDER)
    await settle(page, 1800)
    await shot(page, runner.out / "shots", "settle_record")
    return {"record_path": path, "audit_lines": audit, "framing": framing}


async def scene_duplicate(runner: SceneRunner, page: Page) -> dict:
    """The same invoice arriving twice is caught by the duplicate rule."""
    await goto(page, runner.base, "/upload")
    sample = runner.samples / "sample-duplicate.pdf"
    await page.set_input_files("input[type=file]", str(sample))
    await settle(page, 800)
    btn = page.locator("button", has_text=re.compile(r"Process .*invoice", re.I))
    await human_click(page, btn.first, ms=1200)
    lines = await wait_stream_complete(page)
    await settle(page, 900)
    link = page.locator("a", has_text=re.compile(r"open record", re.I)).first
    href = await link.get_attribute("href")
    await human_click(page, link, ms=1500)
    await page.wait_for_load_state("domcontentloaded")
    await settle(page, 2000)
    audit = await read_record_audit(page)
    framing = await push_in_finder(page, RECORD_LINES_FINDER)
    await settle(page, 1800)
    await shot(page, runner.out / "shots", "duplicate_record")
    runner.state["last_invoice_path"] = href
    return {"sample": sample.name, "stream_lines": lines, "record_path": href,
            "audit_lines": audit, "framing": framing}


async def scene_hold(runner: SceneRunner, page: Page) -> dict:
    """A new vendor never settles on its own: it is held, with the sentence."""
    await goto(page, runner.base, "/upload")
    sample = runner.samples / "sample-new-vendor.pdf"
    await page.set_input_files("input[type=file]", str(sample))
    await settle(page, 800)
    btn = page.locator("button", has_text=re.compile(r"Process .*invoice", re.I))
    await human_click(page, btn.first, ms=1200)
    lines = await wait_stream_complete(page)
    await settle(page, 1500)
    framing = await push_in(page)
    await settle(page, 1600)
    await shot(page, runner.out / "shots", "hold_stream")
    return {"sample": sample.name, "stream_lines": lines, "framing": framing}


async def scene_held(runner: SceneRunner, page: Page) -> dict:
    """The human queue: the reason for the hold is printed next to it."""
    await goto(page, runner.base, "/approvals")
    await settle(page, 1200)
    framing = await push_in_finder(page, HELD_CARD_FINDER)
    await settle(page, 1800)
    await shot(page, runner.out / "shots", "held")
    return {"head": (await page.inner_text("body"))[:500], "framing": framing}


async def scene_evidence(runner: SceneRunner, page: Page) -> dict:
    """The evidence: which rule fired, how often, how confident."""
    await goto(page, runner.base, "/audit")
    await settle(page, 1200)
    # Open on the KPI strip (decisions, automation rate, confidence) rather
    # than mid-list: those numbers are the argument.
    await scroll_steps(page, [0], ms=600)
    await settle(page, 1000)
    await shot(page, runner.out / "shots", "evidence_top")
    kpi = await push_in_finder(page, AUDIT_KPI_FINDER)
    await settle(page, 1600)
    await shot(page, runner.out / "shots", "evidence")
    return {"chars": len(await page.inner_text("body")), "framing": kpi}


SCENES = {
    "register": scene_register,
    "settle": scene_settle,
    "record": scene_record,
    "duplicate": scene_duplicate,
    "hold": scene_hold,
    "held": scene_held,
    "evidence": scene_evidence,
}


async def main_async(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    if out.exists() and args.clean:
        # only remove previous recordings: cards/ and nar/ are produced by the
        # other scripts and must survive a re-take
        for f in out.glob("scene_*.webm"):
            f.unlink()
        for f in out.glob("page@*.webm"):
            f.unlink()
        shots = out / "shots"
        if shots.exists():
            shutil.rmtree(shots)
    out.mkdir(parents=True, exist_ok=True)
    (out / "shots").mkdir(exist_ok=True)

    samples = Path(args.samples).resolve()
    if not samples.is_dir():
        print(f"samples dir not found: {samples}", file=sys.stderr)
        return 2

    wanted = list(SCENES) if args.scenario == "full" else args.scenario.split(",")
    wanted = [s.strip() for s in wanted if s.strip() in SCENES]
    if not wanted:
        print(f"no known scenes selected (known: {', '.join(SCENES)})", file=sys.stderr)
        return 2

    reset = await reset_live_harness_artifacts(args.base_url)
    log(f"harness reset before take: {reset}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb", "--font-render-hinting=none"],
        )
        runner = SceneRunner(browser, out, args.base_url.rstrip("/"), samples, args.headless)
        for name in wanted:
            try:
                await runner.run(name, SCENES[name])
            except Exception as exc:  # keep going: a failed scene must not kill the take
                log(f"scene {name}: FAILED {exc!r}")
                runner.manifest.append({"name": name, "video": None, "error": repr(exc)})
        await browser.close()

    (out / "manifest.json").write_text(json.dumps(runner.manifest, indent=2))
    ok = [m for m in runner.manifest if m.get("video")]
    (out / "take_meta.json").write_text(json.dumps({"harness_reset": reset}, indent=2))
    log(f"recorded {len(ok)}/{len(runner.manifest)} scenes -> {out}")
    for m in runner.manifest:
        print(f"  {m['name']:<10} {m.get('seconds')}s  {m.get('video')}")
    return 0 if len(ok) == len(runner.manifest) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://hermes-vm.tailfd1655.ts.net")
    ap.add_argument("--out", default="/home/hermes/.hermes/cache/scratch/demo_take")
    ap.add_argument("--samples", default="/home/hermes/invoiceflow/backend/demo-data/sample_invoices")
    ap.add_argument("--scenario", default="full", help="full or comma-separated scene names")
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--headed", dest="headless", action="store_false")
    ap.add_argument("--clean", action="store_true", default=True)
    ap.add_argument("--no-clean", dest="clean", action="store_false")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())