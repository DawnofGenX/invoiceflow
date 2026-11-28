#!/usr/bin/env python3
"""Render the InvoiceFlow demo title/architecture/outro cards as 1920x1080 PNGs.

The cards are plain HTML rendered with the product's own design tokens
(DESIGN.md: print #f2f2ea, ink #0f1e1b, rule #d5d7ca, Archivo + Sometype Mono)
and screenshotted with Playwright, so the video reads as one artefact with the
app instead of a pile of slides.

Usage (Playwright lives on /usr/bin/python3 on this machine):
    /usr/bin/python3 scripts/make_cards.py --out /home/hermes/.hermes/cache/scratch/demo_take/cards
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

W, H = 1920, 1080

TOKENS = {
    "print": "#f2f2ea",
    "print2": "#e9e9df",
    "slip": "#fbfbf5",
    "ink": "#0f1e1b",
    "ink-soft": "#1e312d",
    "ink-mute": "#46554f",
    "rail": "#a9bab3",
    "rule": "#d5d7ca",
    "rule-firm": "#b3b7a8",
    "settled": "#2a6350",
    "hold": "#8a5b10",
    "void": "#a23a22",
    "signal": "#b4481f",
}

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1920px; height: 1080px; }
body {
  background: {print};
  color: {ink};
  font-family: Archivo, Inter, system-ui, sans-serif;
  display: flex; flex-direction: column;
  padding: 72px 96px;
  position: relative;
}
.mono { font-family: "Sometype Mono", ui-monospace, monospace; }
.eyebrow { font-family: "Sometype Mono", ui-monospace, monospace; font-size: 22px;
  letter-spacing: 0.22em; text-transform: uppercase; color: {ink-mute}; }
h1 { font-size: 104px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.02; }
h2 { font-size: 62px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.08; }
p { font-size: 30px; line-height: 1.5; color: {ink-mute}; max-width: 1400px; }
.rule { height: 1px; background: {rule-firm}; }
.rail { position: absolute; left: 0; top: 0; bottom: 0; width: 26px; background: {ink}; }
.foot { position: absolute; left: 96px; right: 96px; bottom: 60px;
  display: flex; justify-content: space-between; align-items: baseline;
  font-family: "Sometype Mono", ui-monospace, monospace; font-size: 22px; color: {ink-mute}; }
"""


def page_html(body: str, extra_css: str = "") -> str:
    css = BASE_CSS + extra_css
    for k, v in TOKENS.items():
        css = css.replace("{" + k + "}", v)
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"


def title_card() -> str:
    body = f"""
    <div class="rail"></div>
    <div class="eyebrow">Zyrelyx Global AI Hackathon &middot; December 2026</div>
    <div style="height:56px"></div>
    <h1>InvoiceFlow</h1>
    <div style="height:26px"></div>
    <p style="font-size:40px; max-width:1500px; color:{TOKENS['ink-soft']}">
      An open-source, explainable multi-agent accounts payable platform.
      Every decision is printed with the rule that fired, the confidence,
      and the sentence that stopped it.
    </p>
    <div style="height:44px"></div>
    <div class="rule" style="width:520px"></div>
    <div style="height:26px"></div>
    <div class="mono" style="font-size:26px; color:{TOKENS['ink-mute']}">
      live &mdash; https://hermes-vm.tailfd1655.ts.net &nbsp;&middot;&nbsp; github.com/DawnofGenX/invoiceflow
    </div>
    """
    return page_html(body)


def problem_card() -> str:
    rows = [
        ("The gap",
         "BILL, Stampli, Ramp, Melio and Rossum all decide whether to pay an invoice. "
         "None of them will tell you why."),
        ("The cost",
         "A controller who cannot reconstruct a decision cannot sign the batch. "
         "Audit standards ask for the reasoning, not the outcome."),
        ("The answer",
         "InvoiceFlow is a register, not a queue. Every agent decision lands as a ruled, "
         "readable entry with the rule, the confidence and the sentence behind it."),
    ]
    body = f"""
    <div class="rail"></div>
    <div class="eyebrow">Why this exists</div>
    <div style="height:34px"></div>
    <h2 style="max-width:1500px">Accounts payable tools decide.<br>None of them explain.</h2>
    <div style="height:54px"></div>
    <div style="display:flex; flex-direction:column; gap:30px; max-width:1560px">
    {''.join(
        f'''<div style="display:flex; gap:34px; align-items:baseline">
             <div class="mono" style="font-size:22px; letter-spacing:.18em; text-transform:uppercase;
                  color:{TOKENS['signal']}; width:210px; flex:none">{k}</div>
             <div style="font-size:31px; line-height:1.45; color:{TOKENS['ink-soft']}">{v}</div>
           </div><div class="rule"></div>''' for k, v in rows)}
    </div>
    """
    return page_html(body)


def architecture_card() -> str:
    stages = [
        ("INTAKE", "classify_document", "not_an_invoice"),
        ("EXTRACTION", "extract_fields", "vision + reasoning"),
        ("VALIDATION", "5 ordered checks", "po_match / duplicate / amount"),
        ("APPROVAL", "new_vendor, then threshold", "auto_approve &lt; $500"),
    ]
    cells = "".join(
        f'''<div style="flex:1; background:{TOKENS['slip']}; border:1px solid {TOKENS['rule-firm']};
              padding:26px 28px; border-radius:4px">
             <div class="mono" style="font-size:20px; letter-spacing:.16em; color:{TOKENS['settled']}">{a}</div>
             <div style="height:14px"></div>
             <div style="font-size:29px; font-weight:600; letter-spacing:-.01em">{b}</div>
             <div style="height:10px"></div>
             <div class="mono" style="font-size:19px; color:{TOKENS['ink-mute']}; line-height:1.5">{c}</div>
           </div>''' for a, b, c in stages
    )
    body = f"""
    <div class="rail"></div>
    <div class="eyebrow">How it is built</div>
    <div style="height:30px"></div>
    <h2>One LangGraph state machine.<br>Every node commits its own audit rows.</h2>
    <div style="height:46px"></div>
    <div style="display:flex; gap:20px">{cells}</div>
    <div style="height:34px"></div>
    <div class="rule"></div>
    <div style="height:26px"></div>
    <div style="display:flex; gap:56px">
      <div style="flex:1">
        <div class="mono" style="font-size:20px; letter-spacing:.16em; color:{TOKENS['ink-mute']}">RESILIENCE</div>
        <div style="height:12px"></div>
        <div style="font-size:26px; line-height:1.45; color:{TOKENS['ink-soft']}">
          Bounded retry with backoff on 429 and 5xx, per-call timeouts, and a
          deterministic fallback that degrades the decision instead of failing the request.
        </div>
      </div>
      <div style="flex:1">
        <div class="mono" style="font-size:20px; letter-spacing:.16em; color:{TOKENS['ink-mute']}">REPRODUCIBLE</div>
        <div style="height:12px"></div>
        <div style="font-size:26px; line-height:1.45; color:{TOKENS['ink-soft']}">
          A stub mode runs the whole pipeline with no API key, and the smoke suite
          asserts the product's own decisions, not mocks.
        </div>
      </div>
    </div>
    """
    return page_html(body)


def outro_card() -> str:
    body = f"""
    <div class="rail"></div>
    <div class="eyebrow">Try it yourself</div>
    <div style="height:52px"></div>
    <h1 style="font-size:92px">Read why.</h1>
    <div style="height:24px"></div>
    <p style="font-size:38px; color:{TOKENS['ink-soft']}; max-width:1420px">
      Upload an invoice. Watch four agents reason in writing. Read the rule that
      fired, the confidence, and the sentence that stopped it.
    </p>
    <div style="height:52px"></div>
    <div class="rule" style="width:600px"></div>
    <div style="height:30px"></div>
    <div class="mono" style="font-size:28px; line-height:1.7; color:{TOKENS['ink-mute']}">
      live &mdash; https://hermes-vm.tailfd1655.ts.net<br>
      source &mdash; github.com/DawnofGenX/invoiceflow<br>
      <span style="color:{TOKENS['settled']}">MIT licensed &middot; bring your own key, or run it in stub mode</span>
    </div>
    """
    return page_html(body)


CARDS = {
    "title": title_card,
    "problem": problem_card,
    "architecture": architecture_card,
    "outro": outro_card,
}


async def main_async(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--force-color-profile=srgb"])
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for name, fn in CARDS.items():
            await page.set_content(fn(), wait_until="load")
            await page.wait_for_timeout(500)
            path = out / f"card_{name}.png"
            await page.screenshot(path=str(path))
            print(f"{name}: {path} ({path.stat().st_size} bytes)")
        await browser.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/home/hermes/.hermes/cache/scratch/demo_take/cards")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())