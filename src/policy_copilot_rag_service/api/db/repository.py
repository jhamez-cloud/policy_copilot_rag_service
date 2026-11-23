"""Database queries; callers own transaction commits and validation."""

from collections.abc import Iterable
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ChatSession, Document, Library

SYSTEM_LIBRARY_KEY = "software-policy"
SYSTEM_LIBRARY_NAME = "Software policy"


class SystemLibraryError(ValueError):
    """A caller attempted to mutate project-managed policies or their library."""


def require_mutable_library(library: Library) -> None:
    if library.is_system:
        raise SystemLibraryError("The Software policy library is managed by the project and is read-only.")


def require_mutable_document(document: Document) -> None:
    if document.source == "seed" or (document.library is not None and document.library.is_system):
        raise SystemLibraryError("Software policy documents are managed by the project and cannot be changed or removed.")


def ensure_system_library(db: Session) -> Library:
    """Create one built-in library and repair seeded membership without committing."""
    library = db.scalar(select(Library).where(Library.system_key == SYSTEM_LIBRARY_KEY))
    if library is None:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise NotImplementedError(f"System library setup is not supported for {dialect}")
        db.execute(
            insert(Library)
            .values(name=SYSTEM_LIBRARY_NAME, system_key=SYSTEM_LIBRARY_KEY)
            .on_conflict_do_nothing(index_elements=["system_key"])
        )
        library = db.scalar(select(Library).where(Library.system_key == SYSTEM_LIBRARY_KEY))
    if library is None:
        raise RuntimeError("Software policy library could not be initialized")

    library.name = SYSTEM_LIBRARY_NAME
    # Use ORM relationships so loaded links are repaired alongside SQL IDs.
    for document in db.scalars(select(Document).where(Document.source == "seed")):
        if document.library_id != library.id:
            document.library = library
    db.flush()
    return library

def get_doc_by_id(db:Session,doc_id:int) -> Document | None:
    return db.get(Document, doc_id)


def get_doc_by_hash(db:Session,content_hash:str) -> Document | None:
    return db.scalar(select(Document).where(Document.content_hash == content_hash))


def add_doc(db:Session, **fields):
    doc = Document(**fields)
    db.add(doc)
    db.flush()

    return doc


def get_docs_list(
    db: Session,
    category: str | None,
    limit: int,
    offset: int,
    *,
    library_id: int | None = None,
    uncategorized: bool = False,
) -> tuple[int, List[Document]]:
    rows = select(Document)
    rows_count = select(func.count()).select_from(Document)

    if category:
        rows = rows.where(Document.category == category)
        rows_count = rows_count.where(Document.category == category)

    if library_id is not None:
        rows = rows.where(Document.library_id == library_id)
        rows_count = rows_count.where(Document.library_id == library_id)

    if uncategorized:
        rows = rows.where(Document.library_id.is_(None))
        rows_count = rows_count.where(Document.library_id.is_(None))

    rows_list = db.scalars(rows.order_by(Document.id.desc()).limit(limit).offset(offset)).all()
    total_count = db.scalar(rows_count) or 0

    return total_count,list(rows_list)


def get_all_docs(db:Session) -> List[Document] | None:
    return list(db.scalars(select(Document).order_by(Document.id)).all())


def get_doc_count(db:Session) -> int:
    return db.scalar(select(func.count()).select_from(Document)) or 0


def delete_doc(db:Session,doc:Document) -> None:
    require_mutable_document(doc)
    db.delete(doc)


def get_docs_by_ids(db: Session, ids: Iterable[int]) -> list[Document]:
    document_ids = list(ids)
    if not document_ids:
        return []
    return list(
        db.scalars(
            select(Document).where(Document.id.in_(document_ids)).order_by(Document.id)
        ).all()
    )


def get_library_by_id(db: Session, library_id: int) -> Library | None:
    return db.get(Library, library_id)


def add_library(db: Session, name: str) -> Library:
    library = Library(name=name)
    db.add(library)
    db.flush()
    return library


def get_libraries_list(
    db: Session, limit: int, offset: int
) -> tuple[int, list[Library]]:
    rows = db.scalars(
        select(Library).order_by(Library.id.desc()).limit(limit).offset(offset)
    ).all()
    total = db.scalar(select(func.count()).select_from(Library)) or 0
    return total, list(rows)


def delete_library(db: Session, library: Library) -> None:
    require_mutable_library(library)
    for document in library.documents:
        require_mutable_document(document)
    # Clear both ORM relationships as well as their SQL links, including when
    # objects stay loaded after commit (the session factory disables expiry).
    for document in list(library.documents):
        document.library = None
    for chat_session in list(library.sessions):
        chat_session.library = None
    db.delete(library)


def assign_documents_to_library(
    db: Session, library_id: int, docs: Iterable[Document]
) -> list[Document]:
    library = get_library_by_id(db, library_id)
    if library is None:
        raise ValueError(f"Library with ID {library_id} does not exist")
    require_mutable_library(library)
    documents = list(docs)
    for document in documents:
        require_mutable_document(document)
    for document in documents:
        document.library = library
    db.flush()
    return documents


def remove_documents_from_library(
    db: Session, library_id: int, docs: Iterable[Document]
) -> list[Document]:
    library = get_library_by_id(db, library_id)
    if library is None:
        raise ValueError(f"Library with ID {library_id} does not exist")
    require_mutable_library(library)
    documents = list(docs)
    for document in documents:
        require_mutable_document(document)
    for document in documents:
        if document.library_id == library_id:
            document.library = None
    db.flush()
    return documents


def get_library_documents(
    db: Session, library_id: int, limit: int, offset: int
) -> tuple[int, list[Document]]:
    return get_docs_list(db, None, limit, offset, library_id=library_id)


def get_document_ids_for_library(db: Session, library_id: int | None) -> list[int]:
    return list(
        db.scalars(
            select(Document.id)
            .where(Document.library_id == library_id, Document.source != "seed")
            .order_by(Document.id)
        ).all()
    )


def get_policy_document_ids(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(Document.id).where(Document.source == "seed").order_by(Document.id)
        ).all()
    )


def get_chat_session_by_id(db: Session, session_id: int) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def add_chat_session(db: Session, library_id: int) -> ChatSession:
    chat_session = ChatSession(library_id=library_id)
    db.add(chat_session)
    db.flush()
    return chat_session


def get_chat_sessions_list(
    db: Session, limit: int, offset: int
) -> tuple[int, list[ChatSession]]:
    rows = db.scalars(
        select(ChatSession).order_by(ChatSession.id.desc()).limit(limit).offset(offset)
    ).all()
    total = db.scalar(select(func.count()).select_from(ChatSession)) or 0
    return total, list(rows)


def delete_chat_session(db: Session, chat_session: ChatSession) -> None:
    db.delete(chat_session)
