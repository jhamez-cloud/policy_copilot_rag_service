from dataclasses import dataclass
from functools import lru_cache
from langchain.text_splitter import RecursiveCharacterTextSplitter,Language
from ..settings import get_settings
from typing import List

@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict

@lru_cache(maxsize=1)
def _get_splitter():
    settings = get_settings()

    splitter = RecursiveCharacterTextSplitter.from_language(
        language = Language.MARKDOWN,
        chunk_size = settings.chunk_size,
        chunk_overlap = settings.chunk_overlap
    )

    return splitter


def chunk_document(doc_id:int,title:str,category:str,content:str) -> List[Chunk]:
    chunks = [chunk for chunk in _get_splitter().split_text(content) if chunk.strip()]

    return [Chunk(
        id = f"doc{doc_id}_chunk_{i}",
        text = chunk,
        metadata = {
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "chunk_index": i
        }
    ) for i,chunk in enumerate(chunks,1)]
