'''Documentation String'''
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...settings import get_settings
from ...rag.pipeline import RagPipeline
from ..db.models import Document
from ..db import repository as repo


logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".md",".txt",".markdown"}

@dataclass(frozen=True)
class IngestOutcome:
    filename: str
    status: str
    detail: str = ""
    document: Document | None = None


def derive_title(content:str,filename:str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:255]

    return Path(filename).stem.replace("-"," ").replace("_"," ")


def content_hash(content:str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def prepare(filename:str,raw:bytes) -> tuple[str,str,str]:
    '''Validation of uploaded files and documents to get valid data'''
    settings = get_settings()
    file_extension = Path(filename).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported File Type or Extension: {file_extension}. Allowed: '.md','.markdown','.txt'")

    if len(raw) > settings.max_upload_bytes:
        raise ValueError("File size too large. Compress and upload again.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise ValueError(f"Could not decode file content: {err}")

    content = text.replace("\r\n","\n").strip()

    if not content:
        raise ValueError("File content is empty.")

    return content,derive_title(content,filename),content_hash(content)


def ingest_file(db:Session,pipeline:RagPipeline,filename:str,raw:bytes,category:str) -> IngestOutcome:
    '''Documentation String'''
    try:
        content,title,digest = prepare(filename,raw)
    except Exception as err:
        return IngestOutcome(filename,"rejected",str(err))

    exists = repo.get_doc_by_hash(db,content_hash(content))

    if exists:
        return IngestOutcome(filename,"duplicate",f"Same content as {exists.id}",exists)

    try:
        doc = repo.add_doc(db,title=title, category=category, filename=filename[:255],
            content=content, content_hash=digest, source="upload", chunk_count=0)
    except IntegrityError:
        db.rollback()
        return IngestOutcome(filename,"duplicate","Same document was already uploaded concurrently.")

    doc_id = doc.id
    try:
        chunk_count = pipeline.index_documents(doc_id,title,category,content)
        db.commit()
    except:
        db.rollback()
        pipeline.remove_document(doc_id)
        logger.exception("Indexing failed for %s, upload rolled back",filename)
        raise

    return IngestOutcome(filename,"indexed","Upload and Indexing successful",doc)


def delete_document(db:Session,pipeline:RagPipeline,doc_id:int) -> bool:
    doc = repo.get_doc_by_id(db,doc_id)
    if doc is None:
        return False

    repo.delete_doc(db,doc)
    db.commit()
    pipeline.remove_document(doc_id)

    return True


def seed_from_directory(db:Session,directory:Path) -> int:
    '''Seeding files into database.Files seeded are policy documents regarding usage of software and product and its services
    rendered from the project, including GDPR, Copyrights and T&C's compliant documents.
    '''

    directory = Path(directory)
    if not directory.exists():
        logger.warning("Seed directory %s does not exist, skipping...",directory)
        return 0

    seeded = 0
    for path in sorted(directory.rglob("*.md")):
        try:
            content,title,digest = prepare(path.name,path.read_bytes())
        except ValueError as err:
            logger.warning("Skipping seed file %s:%s",path,err)
            continue

        if repo.get_doc_by_hash(db,digest):
            continue

        relative_path = path.relative_to(directory)
        category = relative_path.parent.name.lower() if relative_path.parent.name else "general"

        repo.add_doc(db, title=title, category=category, filename=path.name,
            content=content, content_hash=digest, source="seed", chunk_count=0)

        seeded += 1

    db.commit()
    return seeded


def rebuild_index(pipeline:RagPipeline,db:Session) -> tuple[int,int]:
    '''Clear the vector space and rebuild indexes on new upload'''

    pipeline.reset()
    docs =  repo.get_all_docs(db)

    total_chunks = 0
    for doc in docs:
        chunk_count = pipeline.index_documents(doc.id,doc.title,doc.category,doc.content)
        total_chunks += chunk_count

    db.commit()

    return len(docs),total_chunks
