"""
File parser utilities for intake-agent.

Supports: .md / .txt (briefing), .csv, .pdf, .docx
"""

import csv
import io
from pathlib import Path
from typing import Union


def extract_text_from_file(
    source: Union[str, bytes, Path],
    filename: str = "",
) -> str:
    """
    Extract raw text from a file.

    Args:
        source: File path (str/Path) or raw bytes.
        filename: Used to infer file type when source is bytes.

    Returns:
        Extracted text content.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        filename = filename or path.name
        data = path.read_bytes()
    else:
        data = source

    ext = Path(filename).suffix.lower()

    if ext in (".md", ".txt", ""):
        return data.decode("utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf(data)

    if ext == ".docx":
        return _extract_docx(data)

    if ext == ".csv":
        return _extract_csv(data)

    # Fallback: try UTF-8
    return data.decode("utf-8", errors="replace")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        return "[PDF extraction requires pypdf. Install with: pip install pypdf]"
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        return "[Word extraction requires python-docx. Install with: pip install python-docx]"
    except Exception as e:
        return f"[Word extraction error: {e}]"


def _extract_csv(data: bytes) -> str:
    try:
        text = data.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return ""
        # Format as readable text for the AI to parse
        lines = []
        for i, row in enumerate(rows, 1):
            parts = [f"{k}: {v}" for k, v in row.items() if v and v.strip()]
            lines.append(f"Row {i}: " + " | ".join(parts))
        return "\n".join(lines)
    except Exception as e:
        return f"[CSV extraction error: {e}]"


def parse_file(
    source: Union[str, bytes, Path],
    filename: str = "",
) -> dict:
    """
    Parse a file and return metadata + extracted text.

    Returns:
        {
            "filename": str,
            "ext": str,
            "text": str,
            "source_type": "copilot_briefing" | "csv" | "pdf" | "docx",
        }
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        filename = filename or path.name
    else:
        path = None

    ext = Path(filename).suffix.lower()

    source_type_map = {
        ".md": "copilot_briefing",
        ".txt": "copilot_briefing",
        ".csv": "csv",
        ".pdf": "pdf",
        ".docx": "docx",
    }
    source_type = source_type_map.get(ext, "copilot_briefing")
    text = extract_text_from_file(source, filename)

    return {
        "filename": filename,
        "ext": ext,
        "text": text,
        "source_type": source_type,
    }
