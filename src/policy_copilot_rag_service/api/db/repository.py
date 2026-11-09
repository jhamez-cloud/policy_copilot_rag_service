'''A repository of DB queries for document CRUD operations'''
from .models import Document
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from typing import List

def get_doc_by_id(db:Session,doc_id:int) -> Document | None:
    return db.get(Document, doc_id)


def get_doc_by_hash(db:Session,content_hash:str) -> Document | None:
    return db.scalar(select(Document).where(Document.content_hash == content_hash))


def add_doc(db:Session, **fields):
    doc = Document(**fields)
    db.add(doc)
    db.flush()

    return doc


def get_docs_list(db:Session,category:str | None,limit:int,offset:int) -> tuple[int,List[Document]]:
    rows = select(Document)
    rows_count = select(func.count()).select_from(Document)

    if category:
        rows = rows.where(Document.category == category)
        rows_count = rows_count.where(Document.category == category)

    rows_list = db.scalars(rows.order_by(Document.id.desc()).limit(limit).offset(offset)).all()
    total_count = db.scalar(rows_count) or 0

    return total_count,list(rows_list)


def get_all_docs(db:Session) -> List[Document] | None:
    return list(db.scalars(select(Document).order_by(Document.id)).all())


def get_doc_count(db:Session) -> int:
    return db.scalar(select(func.count()).select_from(Document)) or 0


def delete_doc(db:Session,doc:Document) -> None:
    db.delete(doc)