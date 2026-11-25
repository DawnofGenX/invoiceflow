---
version: 1
slug: "frontend-app-page-tsx"
primary_target: "frontend/app/page.tsx"
related_targets: ["frontend/app/audit/page.tsx","frontend/app/upload/page.tsx","frontend/app/approvals/page.tsx"]
---

# Surface: InvoiceFlow queue dashboard (/)

## Scope and mode

Operate. The clerk's working screen: the invoice queue, the selected invoice's confirmation slip, and
the routes that support it (upload, approvals, transparency report). Desktop web, daylight office, all-day use.

## Audience and job

An AP clerk working a queue. Job: decide, per invoice, whether the automation got it right, and move on.
Success: fewer re-reads, no invoice stranded, every outcome defensible afterwards.

## Chosen direction

Confirmation Slip — every invoice decision printed as a settlement confirmation the clerk can read line
by line: reference block, rule token, confidence, reasoning, disposition. Memorable moment: an invoice's
audit lines print into fixed cells in front of the row that just changed, and that row holds a lamp
until acknowledged.

## Direction contract

THESIS: The queue is a confirmation register; every decision prints as a confirmation carrying its rule,
its confidence, and its disposition. Refused: the KPI-card dashboard that reports totals while hiding
the per-decision why.

OWN-WORLD: Pale print ground #F1F2EA under a deep ink-green shell #101F1D; settled #2C6A57 and hold
oxide #B4481F as the only live colours; Archivo for labels and prose, Sometype Mono for references,
amounts, timestamps, confidences and disposition tokens; 1px ink rules, content at radius 4–6px, no
shadow on content; a state is a stamped token (AUTO / ACK / HELD / VOID / DONE), never a coloured pill.

STORY: The clerk sees what is waiting, opens a row, reads its confirmation lines in fixed order —
intake, extraction, five validation rules, route — sees the exact rule that fired and the sentence
explaining it, then approves or leaves it. The transparency report re-uses the same printed lines as
aggregate evidence.

FIRST VIEWPORT: Ink rail across the top: product mark, nav (Queue / Upload / Approvals / Transparency),
live counts. Under it the pipeline line, bending only at 90°, with stage nodes and an interchange where a
human must take over. The body is the register: a ruled dense table (reference, vendor, amount, PO, rule
fired, confidence, disposition, age) on the left two-thirds; the selected invoice's confirmation slip on
the right, printing its audit lines.

FORM: 7 of my grounded list (audit working papers → voucher packet → cheque register → three-way match grid
→ remittance stub → NCR form → telex confirmation). Code-led.
seed: seed:e4d9fa8486b95e24

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict,
DESIGN.md, and every shipping raster carrying its provenance.

## Unresolved

Dark rail vs light rail for nav (build decides by render); whether the confirmation panel is a fixed
right column or a bottom drawer at <1280px.
