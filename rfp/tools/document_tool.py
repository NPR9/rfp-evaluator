"""Document Tool: extract clean text from a supplier PDF.

Primary extractor is PyMuPDF (fast, good reading order); pypdf is the fallback.
Raises DocumentError for anything the pipeline cannot evaluate (not a PDF,
encrypted, corrupt, or no extractable text such as a scanned image).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

from rfp.config import MAX_DOC_CHARS, MIN_DOC_CHARS


class DocumentError(Exception):
    """Raised when a PDF cannot be turned into usable text."""


@dataclass
class ExtractedDocument:
    text: str
    page_count: int
    char_count: int
    extractor: str
    truncated: bool


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"-\n(?=[a-z])", "", text)          # join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)                # collapse spaces
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)             # collapse blank lines
    return text.strip()


def _extract_pymupdf(data: bytes) -> tuple[str, int]:
    import pymupdf  # PyMuPDF

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise DocumentError("PDF is password-protected.")
        pages = [f"[Page {i + 1}]\n{page.get_text('text')}" for i, page in enumerate(doc)]
        return "\n".join(pages), doc.page_count


def _extract_pypdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise DocumentError("PDF is password-protected.")
    pages = [f"[Page {i + 1}]\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages)]
    return "\n".join(pages), len(reader.pages)


def extract_pdf_text(data: bytes, filename: str = "document.pdf") -> ExtractedDocument:
    if not data:
        raise DocumentError(f"'{filename}' is empty (0 bytes).")
    if not data.lstrip()[:5].startswith(b"%PDF"):
        raise DocumentError(f"'{filename}' is not a valid PDF file.")

    errors = []
    for name, fn in (("pymupdf", _extract_pymupdf), ("pypdf", _extract_pypdf)):
        try:
            raw, pages = fn(data)
            text = _clean(raw)
            # Remove the page markers when judging whether real content exists.
            content_chars = len(re.sub(r"\[Page \d+\]", "", text).strip())
            if content_chars < MIN_DOC_CHARS:
                errors.append(f"{name}: only {content_chars} characters of text")
                continue
            truncated = len(text) > MAX_DOC_CHARS
            if truncated:
                text = text[:MAX_DOC_CHARS]
            return ExtractedDocument(text, pages, len(text), name, truncated)
        except DocumentError:
            raise
        except ImportError as exc:
            errors.append(f"{name}: not installed ({exc})")
        except Exception as exc:  # corrupt file, parser error
            errors.append(f"{name}: {exc}")

    raise DocumentError(
        f"No usable text could be extracted from '{filename}' "
        f"(it may be scanned, blank or corrupt). Details: {'; '.join(errors)}"
    )
