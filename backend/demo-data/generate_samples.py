"""Generate sample invoice PDFs (text layer) for the demo + API smoke test."""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent / "sample_invoices"


def _write_pdf(name: str, lines: list[str]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    c = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - 60
    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(60, y, line)
        y -= 18
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = height - 60
    c.save()
    return path


def main() -> None:
    _write_pdf("sample-clean.pdf", [
        "INVOICE",
        "Acme Industrial Supply",
        "123 Main Street, Chicago, IL 60601",
        "",
        "Invoice Number: INV-2024-001",
        "Invoice Date: 2024-11-15",
        "Due Date: 2024-12-15",
        "PO Number: PO-1042",
        "",
        "Description        Qty   Unit Price   Total",
        "Steel Bracket      10    15.00        150.00",
        "Hex Bolts M8       200   1.50         300.00",
        "",
        "Total: $450.00",
    ])

    _write_pdf("sample-new-vendor.pdf", [
        "INVOICE",
        "Nova Robotics LLC",
        "45 Innovation Drive, Austin, TX 78701",
        "",
        "Invoice Number: INV-2024-101",
        "Invoice Date: 2024-11-16",
        "Due Date: 2024-12-16",
        "",
        "Description        Qty   Unit Price   Total",
        "Servo Motor Kit    2     100.00       200.00",
        "",
        "Total: $200.00",
    ])

    _write_pdf("sample-duplicate.pdf", [
        "INVOICE",
        "Acme Industrial Supply",
        "123 Main Street, Chicago, IL 60601",
        "",
        "Invoice Number: INV-2024-000",
        "Invoice Date: 2024-11-10",
        "Due Date: 2024-12-10",
        "",
        "Description             Qty   Unit Price   Total",
        "Industrial Fasteners    1     400.00       400.00",
        "",
        "Total: $400.00",
    ])

    _write_pdf("sample-high-value.pdf", [
        "INVOICE",
        "Cobalt Logistics",
        "800 Harbor Blvd, Long Beach, CA 90802",
        "",
        "Invoice Number: INV-2024-030",
        "Invoice Date: 2024-11-17",
        "Due Date: 2024-12-17",
        "PO Number: PO-3301",
        "",
        "Description              Qty   Unit Price   Total",
        "Freight - LTL shipment   1     8750.00      8750.00",
        "",
        "Total: $8750.00",
    ])

    _write_pdf("sample-contract.pdf", [
        "SERVICE AGREEMENT",
        "This agreement is entered into between Party A and Party B.",
        "Party A agrees to provide consulting services to Party B.",
        "Terms and conditions apply. Governing law: State of California.",
        "",
        "This is a legal contract, not an invoice.",
    ])

    print(f"Sample PDFs written to {OUT}")


if __name__ == "__main__":
    main()
