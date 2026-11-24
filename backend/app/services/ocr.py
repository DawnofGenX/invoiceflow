"""Text extraction: Tesseract OCR for images, pypdf for PDFs."""
import subprocess
from pathlib import Path

from app.config import settings


class OCRError(Exception):
    """Raised when text extraction fails."""


def extract_image_text(image_path: str) -> str:
    """Run Tesseract OCR on an image file, return the extracted text."""
    try:
        proc = subprocess.run(
            [settings.tesseract_path, str(image_path), "stdout"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as e:
        raise OCRError(f"Tesseract not found at {settings.tesseract_path}") from e
    except subprocess.TimeoutExpired as e:
        raise OCRError("Tesseract timed out after 120s") from e
    if proc.returncode != 0:
        raise OCRError(f"Tesseract failed: {proc.stderr[:500]}")
    return proc.stdout


def _extract_pdf_text(file_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise OCRError(
            "PDF has no embedded text layer (scanned). "
            "Rasterize the PDF to an image and upload as PNG/JPG, or add poppler."
        )
    return text


def extract_document_text(file_path: str) -> str:
    """Extract text from an uploaded document (PDF or image)."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf_text(file_path)
    if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        return extract_image_text(file_path)
    raise OCRError(f"Unsupported file type: {ext}")
