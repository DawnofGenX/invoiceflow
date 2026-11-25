---
name: InvoiceFlow — Confirmation Register
description: An accounts payable queue that prints every agent decision into a ruled confirmation register, so a clerk can read why an invoice settled, held, or voided.
colors:
  print: "#f2f2ea"
  print-2: "#e9e9df"
  slip: "#fbfbf5"
  ink: "#0f1e1b"
  ink-soft: "#1e312d"
  ink-mute: "#46554f"
  rail-text: "#a9bab3"
  rule: "#d5d7ca"
  rule-firm: "#b3b7a8"
  field: "#7c8375"
  settled: "#2a6350"
  settled-soft: "#dce6df"
  hold: "#8a5b10"
  hold-soft: "#efe5cb"
  void: "#a23a22"
  void-soft: "#f1dad2"
  signal: "#b4481f"
typography:
  display:
    fontFamily: "Archivo, ui-sans-serif, system-ui"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  reasoning:
    fontFamily: "Archivo, ui-sans-serif, system-ui"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  micro:
    fontFamily: "Sometype Mono, ui-monospace, monospace"
    fontSize: "10.5px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.12em"
  data:
    fontFamily: "Sometype Mono, ui-monospace, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  amount:
    fontFamily: "Sometype Mono, ui-monospace, monospace"
    fontSize: "18px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.01em"
rounded:
  token: "2px"
  control: "3px"
  slip: "6px"
spacing:
  hair: "1px"
  row: "36px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.print}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
    typography: "{typography.micro}"
  button-primary-hover:
    backgroundColor: "{colors.ink-soft}"
    textColor: "{colors.print}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
  button-quiet:
    backgroundColor: "{colors.print}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    typography: "{typography.micro}"
  button-void:
    backgroundColor: "{colors.print}"
    textColor: "{colors.void}"
    rounded: "0px"
    padding: "8px 12px"
    typography: "{typography.micro}"
  input-search:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.ink}"
    rounded: "0px"
    padding: "6px 10px"
    typography: "{typography.data}"
  select-filter:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.ink}"
    rounded: "0px"
    padding: "6px 8px"
    typography: "{typography.data}"
  status-token:
    backgroundColor: "{colors.settled-soft}"
    textColor: "{colors.settled}"
    rounded: "{rounded.token}"
    padding: "2px 6px"
    typography: "{typography.micro}"
  nav-rail:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.rail-text}"
    rounded: "0px"
    padding: "0 20px"
    typography: "{typography.micro}"
---

## Overview

**Creative North Star: "The Confirmation Register"**

InvoiceFlow's queue is not a dashboard of KPI cards; it is a register of confirmations. The product's whole claim is that every decision an agent made is readable after the fact — so the interface is built like the paperwork that has always carried trust in accounts payable: a pale print ground, an ink-green shell, hairlines that separate one record from the next, and confirmation lines printed into fixed cells in the order they happened.

The register refuses the category default twice. It has no hero metric grid, and it never summarises a decision into a coloured pill: a disposition is a stamped token (SETTLED, HELD, VOID, DONE) with a square swatch, the way a clerk would stamp a slip. Colour is reserved for state and carries meaning — settled green, hold oxide, void red — while every other surface stays print and ink.

The signature move is the split-flap idea used as a working tool: while an invoice runs, each agent line prints into a fixed cell, letter-clip left to right, so the trail is being written in front of the reader rather than appearing as a finished block. A row whose disposition changed keeps a signal lamp lit until someone acknowledges it.

**Key Characteristics:**
- Print-and-ink world: pale #f2f2ea ground, ink-green shell, 1px rules instead of card shadows.
- Two voices: Archivo sets labels and prose; Sometype Mono sets every reference, amount, timestamp, confidence and token.
- Dispositions are stamps, never pills, and colour only ever means state.
- Density for a clerk working a queue all day: 36px rows, tabular numerals, no wasted verticals.
- Motion conveys state only: the print-in cascade on new decision lines and a lamp pulse for unacknowledged changes.

**The Registers, Not Dashboards Rule.** A screen in this product is a ruled record with a fixed reading order. If an arrangement could belong to any SaaS dashboard — equal-weight KPI cards, a big number with a small label, gradient accents — it is wrong here.

**The Stamp Rule.** State is shown as a stamped mono token with a square swatch beside it. Pills, dots alone, and colour blocks without a word are not dispositions.

**The Monospace Means Data Rule.** Sometype Mono appears only where a value must be compared column-to-column or read back verbatim: references, amounts, dates, confidences, rule names, tokens. Prose is always Archivo.

## Colors

The palette is a print shop's: two papers, one ink, one rule grey, three state hues.

- **Print (#f2f2ea)** is the page. **Print-2 (#e9e9df)** is the same paper in shadow: table headers, hovered rails, dead zones.
- **Slip (#fbfbf5)** is a raised form — the confirmation slip, the dropzone, input grounds. It is brighter than the page so a slip reads as a separate document without a shadow.
- **Ink (#0f1e1b)** is structure and voice: the nav rail, primary buttons, headings, selected rows (a selected register row inverts to ink ground with print text). **Ink-soft (#1e312d)** is its hover. **Ink-mute (#46554f)** carries secondary prose at 6.98:1 on print.
- **Rule (#d5d7ca)** draws hairline separators; **rule-firm (#b3b7a8)** draws table frames and heavier dividers. **Field (#7c8375)** is the only control-outline colour, chosen to clear 3:1 (3.48:1 on print) for WCAG 1.4.11 — rules are decoration, fields are affordances, and they must not be confused.
- **Settled (#2a6350, on settled-soft #dce6df)**, **hold (#8a5b10 on #efe5cb)**, **void (#a23a22 on #f1dad2)** are the three states. **Signal (#b4481f)** is the lamp and the caret: attention that has not been acknowledged yet, never body text.

**The Two Jobs Rule.** Colour either states a disposition or marks something unacknowledged. Nothing is coloured for decoration, importance, or category.

## Typography

Two families, both loaded through `next/font/google` and exposed as `--font-archivo` / `--font-sometype`.

- **Archivo** sets everything read as language: the 26px page title (weight 600, tracking −0.02em), 13px page prose, 12.5px reasoning sentences (max 68ch), 15px slip vendor names.
- **Sometype Mono** sets everything read as data: `.num` class, tabular numerals on, 11.5px references, 12px amounts in the register, 18px amounts on a held slip, 10.5px `.micro` labels in uppercase with 0.12em tracking for column heads, nav, and tokens.
- The scale is fixed rem/px, not fluid: 26 / 18 / 15 / 13 / 12.5 / 12 / 11.5 / 11 / 10.5. Density comes from rhythm, not from shrinking type below 11px.

**The Fixed Cell Rule.** Numeric columns are right-aligned mono with tabular numerals so digits line up down the register; a proportional face in a numeric column is a defect.

## Layout

- Page shell: a 52px ink rail pinned at the top, then a `max-w-[1440px]` body with 20–32px padding.
- The register page is two columns at `lg`: `minmax(0,1fr)` for the table and a 400px sticky aside holding the selected confirmation slip. Below `lg` they stack, slip first when a row is selected.
- The pipeline is drawn as one line with 90° elbows (an SVG, 760×66) at `md` and up, with a spur dropping to a HUMAN interchange node exactly where a person takes over; on small screens it becomes a ruled row of label/value pairs.
- Vertical rhythm: 40px above a page title, 8px under it, 24px between major blocks, and more space above a heading than below.
- Table rows are 36px; cells hold 7px of padding so a 10-row register fits a laptop viewport without scroll.

## Elevation & Depth

The system is flat. There is no box-shadow on any content surface: depth is carried by paper tone (print → print-2 → slip) and by 1px rules. Only the nav rail separates itself, and it does so with colour, not blur or drop shadow.

**The Layered Paper Rule.** To lift something, put it on a brighter paper and rule its edge. Never float it with a shadow, a blur, or a backdrop filter.

## Shapes

- Corners are nearly square: 2px on tokens and swatches, 3px on buttons and chips, 6px on a slip. Anything above 8px belongs to a different product.
- Hairlines are 1px and never coloured as a left or right border on a card: state is a stamp in the flow of the record, not a stripe down its edge.
- Icons are drawn by hand as SVG at 1.25 stroke weight inside 14–20px boxes (document mark, tray, remove, arrow). No icon font, no emoji, no unicode glyph standing in for a control.

## Components

- **Ink rail (nav)**: 52px, ink ground, hand-drawn document mark plus "InvoiceFlow" and a mono "CONFIRMATION REGISTER" kicker; links are 10.5px micro caps in rail-text, the active one a print chip on ink. Right side: "held for review" with a signal lamp and a zero-padded count that refreshes on `invoiceflow:changed` and on a 15s interval.
- **Register table**: dense 36px rows, hairline separators, a lamp gutter for rows whose disposition changed, columns lamp / reference / vendor / amount / PO / confidence / disposition / age. A selected row inverts to ink. Rows are focusable (`tabIndex=0`) and select on Enter or Space as well as click.
- **Status token**: mono, uppercase, 10px, 2px radius, soft ground plus a 5px square swatch, optionally inverted onto ink. Dispositions: SETTLED, SCHEDULED, HELD, REVIEW, VOID, ERROR, PRINTING.
- **Confirmation slip**: header ruled under the reference with the disposition token on the right, then a ruled field grid (Issued / Vendor / Amount / PO / Confidence), then "Decision lines · N printed" and numbered lines: 01 INTAKE — classify_document — rule token — confidence · duration — reasoning sentence.
- **Primary button**: ink ground, print text, 3px radius, 10.5px micro caps, hover ink-soft, disabled 40% opacity with no hover. Its label names the action ("Process 2 invoices", "Stamping…" while busy).
- **Quiet button**: print ground, rule-firm border, ink text — the secondary path (Seed demo ledger, Intake more).
- **Void button**: no fill, void-coloured hairline and text; it is destructive and never the default weight.
- **Search and filter**: slip ground, 1px field outline, square corners, ink border on focus, no glow.

## Do's and Don'ts

- Do keep one reading order per record: what happened, how sure, which rule.
- Do print reasoning sentences verbatim from the audit table; never paraphrase them in the UI.
- Do reserve colour for state and for the unacknowledged lamp.
- Do use tabular mono for anything that is compared or read back.
- Do give every control default, hover, focus-visible, active, disabled and loading states.
- Don't build a KPI card grid, a big-number hero, or an eyebrow above a heading.
- Don't put a decision in a pill, a dot alone, or a coloured left border.
- Don't add shadows, glass, blur, gradient text, or decorative progress rings.
- Don't use mono as a costume outside data: no mono paragraphs, no mono headings.
- Don't claim compliance or payment execution anywhere in the interface; this build does neither.
