from __future__ import annotations

import io
import logging
import shutil
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}
ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
}

# Native text below this triggers OCR fallback
OCR_MIN_NATIVE_CHARS = 200
OCR_DEFAULT_MAX_PAGES = 12
OCR_RENDER_DPI = 110

def _configure_tesseract() -> None:
    """Point pytesseract at common Windows install paths if needed."""
    try:
        import pytesseract  # type: ignore
    except Exception:
        return
    which = shutil.which("tesseract")
    if which:
        return
    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ):
        if candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


_configure_tesseract()

_rapid_engine = None


def is_allowed_file(filename: str, content_type: str | None) -> bool:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    if content_type and content_type.split(";")[0].strip() not in ALLOWED_MIME:
        if content_type not in ("application/octet-stream", "binary/octet-stream"):
            return False
    return True


def sidecar_path(pdf_path: Path) -> Path:
    return pdf_path.with_name(pdf_path.name + ".ocr.txt")


def read_sidecar(pdf_path: Path) -> str | None:
    side = sidecar_path(pdf_path)
    if side.is_file() and side.stat().st_size > 40:
        return side.read_text(encoding="utf-8", errors="ignore").strip()
    return None


def write_sidecar(pdf_path: Path, text: str) -> Path:
    side = sidecar_path(pdf_path)
    side.write_text(text, encoding="utf-8")
    return side


def _get_rapid_ocr():
    global _rapid_engine
    if _rapid_engine is not None:
        return _rapid_engine
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        _rapid_engine = RapidOCR()
        return _rapid_engine
    except Exception as exc:  # noqa: BLE001
        logger.info("RapidOCR unavailable: %s", exc)
        _rapid_engine = False
        return None


def ocr_image_bytes(data: bytes) -> str:
    """OCR a single image — Tesseract first (fast), RapidOCR fallback."""
    try:
        import pytesseract  # type: ignore

        image = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(image, config="--psm 6")
        if text.strip():
            return text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Tesseract OCR failed: %s", exc)

    engine = _get_rapid_ocr()
    if engine:
        try:
            import numpy as np

            image = Image.open(io.BytesIO(data)).convert("RGB")
            arr = np.asarray(image)
            result, _ = engine(arr)
            if result:
                lines = [row[1] for row in result if len(row) > 1 and row[1]]
                text = "\n".join(lines).strip()
                if text:
                    return text
        except Exception as exc:  # noqa: BLE001
            logger.debug("RapidOCR image failed: %s", exc)
    return ""


def extract_text_from_image(data: bytes) -> str:
    text = ocr_image_bytes(data)
    if text:
        return text
    Image.open(io.BytesIO(data)).verify()
    return ""


def extract_native_pdf_text(data: bytes, max_pages: int | None = None) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    try:
        n = len(doc) if max_pages is None else min(len(doc), max_pages)
        for i in range(n):
            parts.append(doc.load_page(i).get_text("text"))
    finally:
        doc.close()
    return "\n".join(parts).strip()


def ocr_pdf_bytes(
    data: bytes,
    *,
    max_pages: int = OCR_DEFAULT_MAX_PAGES,
    dpi: int = OCR_RENDER_DPI,
) -> str:
    """Rasterize PDF pages and OCR them (scanned textbooks)."""
    if not _get_rapid_ocr():
        # Still try page-by-page via pytesseract if present
        pass

    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    try:
        n = min(len(doc), max_pages)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i in range(n):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png = pix.tobytes("png")
            page_text = ocr_image_bytes(png)
            if page_text:
                parts.append(page_text)
            if (i + 1) % 5 == 0:
                logger.info("OCR progress page %s/%s", i + 1, n)
        if len(doc) > max_pages:
            parts.append(f"\n[OCR truncated: first {max_pages} of {len(doc)} pages]\n")
    finally:
        doc.close()
    return "\n".join(parts).strip()


def extract_text_from_pdf(
    data: bytes,
    *,
    use_ocr: bool = True,
    max_pages: int = OCR_DEFAULT_MAX_PAGES,
    min_native_chars: int = OCR_MIN_NATIVE_CHARS,
) -> tuple[str, str]:
    """Return (text, method) where method is native|ocr|empty."""
    native = extract_native_pdf_text(data, max_pages=max_pages)
    if len(native) >= min_native_chars:
        return native, "native"
    if use_ocr:
        ocr_text = ocr_pdf_bytes(data, max_pages=max_pages)
        if len(ocr_text) >= 40:
            # Prefer OCR if native was empty/near-empty; merge if both sparse
            if len(native) < 40:
                return ocr_text, "ocr"
            merged = (native + "\n\n" + ocr_text).strip()
            return merged, "ocr+native"
        if native:
            return native, "native-low"
    return native, "empty" if not native else "native-low"


def extract_pdf_path(
    path: Path,
    *,
    use_ocr: bool = True,
    max_pages: int = OCR_DEFAULT_MAX_PAGES,
    prefer_sidecar: bool = True,
) -> tuple[str, str]:
    """Extract PDF text from disk, using/caching `.ocr.txt` sidecars."""
    if prefer_sidecar:
        cached = read_sidecar(path)
        if cached:
            return cached, "sidecar"

    data = path.read_bytes()
    text, method = extract_text_from_pdf(data, use_ocr=use_ocr, max_pages=max_pages)
    if method.startswith("ocr") and text:
        try:
            write_sidecar(path, text)
        except OSError as exc:
            logger.warning("Could not write OCR sidecar for %s: %s", path, exc)
    return text, method


def extract_text(filename: str, data: bytes, content_type: str | None = None) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".txt" or (content_type and content_type.startswith("text/")):
        return data.decode("utf-8", errors="ignore").strip()
    if ext == ".pdf" or content_type == "application/pdf":
        text, _ = extract_text_from_pdf(data, use_ocr=True)
        return text
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return extract_text_from_image(data)
    raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks
