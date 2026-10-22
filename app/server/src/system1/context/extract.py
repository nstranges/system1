"""Turns an uploaded file into plain text. The file is data: nothing in it is ever executed or followed."""

import io
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

from docx import Document
from pypdf import PdfReader

from system1.datasets.constants import CONTEXT_MAX_FILE_BYTES
from system1.errors import ApiError

MAX_NAME_CHARS = 200
MAX_DOCX_UNZIPPED_BYTES = 20_000_000
_TEXT_KINDS = {".md": "md", ".markdown": "md", ".txt": "txt"}


class UnsupportedFile(ApiError):
    status_code = 422
    code = "unsupported_file"
    message = "Use a PDF, Word, Markdown or text file."


class EmptyText(ApiError):
    status_code = 422
    code = "empty_text"
    message = "We couldn't read any text from that file. Scanned PDFs aren't supported yet."


class TooMuchText(ApiError):
    status_code = 422
    code = "too_much_text"
    message = "That file has too much text. Try a shorter version."


class UnreadablePdf(ApiError):
    status_code = 422
    code = "unreadable_pdf"
    message = "We couldn't read that PDF."


class UnreadableDocx(ApiError):
    status_code = 422
    code = "unreadable_docx"
    message = "We couldn't read that Word file."


def clean_name(filename: str) -> str:
    """Only the base name is kept, on one line, so it can't forge a `--- name ---` boundary in the prompt."""
    base = PureWindowsPath(PurePosixPath(filename.replace("\\", "/")).name).name
    one_line = "".join(c if c.isprintable() else " " for c in base)
    return " ".join(one_line.split())[:MAX_NAME_CHARS]


def clean_text(text: str) -> str:
    # Lone surrogates can't be encoded as UTF-8 and would fail the database insert.
    text = text.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")
    return text.strip()


def _check_size(length: int) -> None:
    if length > CONTEXT_MAX_FILE_BYTES:
        raise TooMuchText()


def _pdf_text(data: bytes) -> str:
    # Third-party parsers have no stable exception contract (pypdf raises ValueError, KeyError, RecursionError
    # and more on hostile input), so everything they raise becomes one plain message.
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnreadablePdf()
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            part = page.extract_text() or ""
            total += len(part)
            _check_size(total)
            parts.append(part)
        return "\n".join(parts)
    except ApiError:
        raise
    except Exception:  # noqa: BLE001 - boundary around a parser with no stable exception contract
        raise UnreadablePdf() from None


def _docx_text(data: bytes) -> str:
    # Same boundary as the PDF parser. The zip is measured first because a tiny docx can expand to
    # hundreds of megabytes of XML.
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_UNZIPPED_BYTES:
                raise UnreadableDocx()
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except ApiError:
        raise
    except Exception:  # noqa: BLE001 - boundary around a parser with no stable exception contract
        raise UnreadableDocx() from None


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    name = clean_name(filename).lower()
    suffix = PurePosixPath(name).suffix
    if suffix == ".pdf":
        kind, text = "pdf", _pdf_text(data)
    elif suffix == ".docx":
        kind, text = "docx", _docx_text(data)
    elif suffix in _TEXT_KINDS:
        kind, text = _TEXT_KINDS[suffix], data.decode("utf-8", errors="replace")
    else:
        raise UnsupportedFile()
    text = clean_text(text)
    if not text:
        raise EmptyText()
    _check_size(len(text))
    return kind, text
