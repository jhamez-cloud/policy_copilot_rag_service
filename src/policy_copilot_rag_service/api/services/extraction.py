"""Convert supported uploads to readable text before storage and indexing."""

import csv
import io
import logging
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from zipfile import BadZipFile, ZipFile

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc", ".pptx", ".ppt", ".csv", ".txt", ".md", ".markdown")
MAX_ARCHIVE_BYTES = 50_000_000
MAX_ARCHIVE_ENTRIES = 5_000
MAX_PDF_PAGES = 1_000
DOC_TIMEOUT_SECONDS = 30
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def available_extensions() -> list[str]:
    office_available = any(shutil.which(name) for name in ("libreoffice", "soffice"))
    legacy_doc_available = shutil.which("antiword") or office_available
    return [
        extension for extension in SUPPORTED_EXTENSIONS
        if (extension != ".doc" or legacy_doc_available)
        and (extension != ".ppt" or office_available)
    ]


def _decode_text(raw: bytes) -> str:
    try:
        # Excel may export CSV as UTF-16; require a BOM instead of guessing.
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        text = raw.decode(encoding)
    except UnicodeError as error:
        raise ValueError("Text and CSV files must use UTF-8 or BOM-marked UTF-16 encoding.") from error
    if "\x00" in text:
        raise ValueError("The file contains binary data instead of readable text.")
    return text


def _check_archive(raw: bytes) -> None:
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES or sum(entry.file_size for entry in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError("The Office file expands beyond the supported archive limit.")
            if any(entry.flag_bits & 1 for entry in entries):
                raise ValueError("Password-protected Office files are not supported. Upload an unlocked copy.")
    except BadZipFile as error:
        raise ValueError("The Office file is damaged or does not match its extension.") from error


def _join_text(parts, max_chars: int) -> str:
    result = []
    size = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue
        size += len(part) + (2 if result else 0)
        if size > max_chars:
            raise ValueError(f"Extracted text exceeds the {max_chars:,}-character limit. Split the document and upload again.")
        result.append(part)
    return "\n\n".join(result)


def _pdf_parts(raw: bytes):
    from pypdf import PdfReader

    if not raw.lstrip().startswith(b"%PDF-"):
        raise ValueError("The file is not a valid PDF.")
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported. Upload an unlocked copy.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"PDFs may contain at most {MAX_PDF_PAGES:,} pages. Split the PDF and upload again.")
    for page in reader.pages:
        yield page.extract_text() or ""


def _table_text(table) -> str:
    return "\n".join("\t".join(cell.text.strip() for cell in row.cells) for row in table.rows)


def _docx_parts(raw: bytes):
    from docx import Document
    from docx.table import Table

    _check_archive(raw)
    document = Document(io.BytesIO(raw))
    # Keep paragraphs and tables in their original reading order.
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            yield _table_text(block)
        else:
            text = block.text.strip()
            style = block.style.name if block.style is not None else ""
            if text and style.startswith("Heading ") and style[8:].isdigit():
                text = f"{'#' * min(int(style[8:]), 6)} {text}"
            yield text
    for section in document.sections:
        for part in (section.header, section.footer):
            if not part.is_linked_to_previous:
                for block in part.iter_inner_content():
                    yield _table_text(block) if isinstance(block, Table) else block.text


def _shape_parts(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _shape_parts(shape.shapes)
        elif shape.has_table:
            yield _table_text(shape.table)
        elif shape.has_text_frame:
            yield shape.text_frame.text


def _pptx_parts(raw: bytes, max_chars: int):
    from pptx import Presentation

    _check_archive(raw)
    presentation = Presentation(io.BytesIO(raw))
    for number, slide in enumerate(presentation.slides, 1):
        parts = list(_shape_parts(slide.shapes))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and notes.text.strip():
                parts.append(f"Speaker notes: {notes.text}")
        text = _join_text(parts, max_chars)
        if text:
            yield f"## Slide {number}\n{text}"


def _legacy_pptx_bytes(raw: bytes) -> bytes:
    if not raw.startswith(OLE_SIGNATURE):
        raise ValueError("The file is not a valid legacy PowerPoint presentation. Save it as .pptx and upload again.")
    office = shutil.which("libreoffice") or shutil.which("soffice")
    if office is None:
        raise ValueError("Legacy .ppt conversion requires LibreOffice on the server. Save the file as .pptx or install LibreOffice.")

    with TemporaryDirectory(prefix="policy-ppt-") as directory:
        source = Path(directory) / "upload.ppt"
        source.write_bytes(raw)
        converted = Path(directory) / "converted"
        converted.mkdir()
        profile = (Path(directory) / "profile").as_uri()
        try:
            result = subprocess.run(
                [office, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pptx", "--outdir", str(converted), str(source)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=DOC_TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("Legacy PowerPoint conversion timed out. Save the file as .pptx and upload again.") from error

        target = converted / "upload.pptx"
        if result.returncode or not target.is_file():
            raise ValueError("The PowerPoint document is damaged, password-protected, or unsupported. Save it as .pptx and upload again.")
        if target.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("The converted PowerPoint file exceeds the supported archive limit.")
        converted_raw = target.read_bytes()
        _check_archive(converted_raw)
        return converted_raw


def _csv_parts(raw: bytes):
    text = _decode_text(raw)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
    headers = next((row for row in reader if any(cell.strip() for cell in row)), [])
    if not headers:
        return
    headers = [value.strip() or f"Column {index}" for index, value in enumerate(headers, 1)]
    yield "\t".join(headers)
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f"CSV row {reader.line_num} has {len(row)} fields; expected {len(headers)}.")
        yield " | ".join(f"{header}: {value.strip()}" for header, value in zip(headers, row))


def _doc_text(raw: bytes, max_chars: int) -> str:
    if not raw.startswith(OLE_SIGNATURE) and not raw.lstrip().startswith(b"{\\rtf"):
        raise ValueError("The file is not a valid legacy Word document. Save it as .docx and upload again.")
    antiword = shutil.which("antiword")
    office = shutil.which("libreoffice") or shutil.which("soffice")
    if antiword is None and office is None:
        raise ValueError("Legacy .doc conversion requires antiword or LibreOffice on the server. Save the file as .docx or install a converter.")
    started = monotonic()
    with TemporaryDirectory(prefix="policy-doc-") as directory:
        source = Path(directory) / "upload.doc"
        source.write_bytes(raw)
        # Use a generated path, no shell, and bounded output and execution time.
        with (Path(directory) / "output.txt").open("w+b") as output:
            if antiword:
                try:
                    result = subprocess.run(
                        [antiword, "-m", "UTF-8.txt", "-w", "0", str(source)],
                        stdout=output, stderr=subprocess.DEVNULL, timeout=DOC_TIMEOUT_SECONDS, check=False,
                    )
                except subprocess.TimeoutExpired as error:
                    raise ValueError("Legacy Word conversion timed out. Save the file as .docx and upload again.") from error
                if result.returncode == 0:
                    output.seek(0)
                    data = output.read(max_chars * 4 + 1)
                    if len(data) > max_chars * 4:
                        raise ValueError("Extracted Word text exceeds the supported limit. Split the document and upload again.")
                    if data.strip():
                        return _decode_text(data)
            # Antiword cannot read some valid short Word documents or RTF-based
            # .doc files. LibreOffice converts those in an isolated profile.
            if office is None:
                raise ValueError("This Word document requires LibreOffice conversion on the server. Save it as .docx and upload again.")
            converted = Path(directory) / "converted"
            converted.mkdir()
            profile = (Path(directory) / "profile").as_uri()
            try:
                result = subprocess.run(
                    [office, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "txt:Text (encoded):UTF8", "--outdir", str(converted), str(source)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=max(0.001, DOC_TIMEOUT_SECONDS - (monotonic() - started)), check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise ValueError("Legacy Word conversion timed out. Save the file as .docx and upload again.") from error
            target = converted / "upload.txt"
            if result.returncode or not target.is_file():
                raise ValueError("The Word document is damaged, password-protected, or unsupported. Save it as .docx and upload again.")
            with target.open("rb") as converted_text:
                data = converted_text.read(max_chars * 4 + 1)
            if len(data) > max_chars * 4:
                raise ValueError("Extracted Word text exceeds the supported limit. Split the document and upload again.")
            return _decode_text(data)


def extract_text(filename: str, raw: bytes, *, max_chars: int) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {extension or '(none)'}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}.")
    if not raw:
        raise ValueError("File content is empty.")
    try:
        if extension == ".pdf":
            parts = _pdf_parts(raw)
        elif extension == ".docx":
            parts = _docx_parts(raw)
        elif extension == ".pptx":
            parts = _pptx_parts(raw, max_chars)
        elif extension == ".ppt":
            parts = _pptx_parts(_legacy_pptx_bytes(raw), max_chars)
        elif extension == ".doc":
            parts = [_doc_text(raw, max_chars)]
        elif extension == ".csv":
            parts = _csv_parts(raw)
        else:
            parts = [_decode_text(raw)]
        content = _join_text(parts, max_chars).replace("\r\n", "\n").replace("\r", "\n").replace("\v", "\n").replace("\x00", "").strip()
    except ValueError:
        raise
    except Exception as error:
        logger.warning("Unable to extract %s document text (%s)", extension, type(error).__name__)
        raise ValueError(f"Could not read this {extension} file. It may be damaged, encrypted, or mislabeled. Save a fresh copy and try again.") from error
    if not content:
        if extension == ".pdf":
            raise ValueError("This PDF has no readable text. Scanned PDFs require OCR before upload.")
        raise ValueError("The document contains no readable text. Image-only documents require OCR before upload.")
    return content
