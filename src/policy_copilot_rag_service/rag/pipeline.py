'''Complete RAG Pipeline'''
import logging
import threading
from dataclasses import dataclass

from ..settings import get_settings
from .chunking import chunk_document
from .embeddings import embed_query,embed_texts
from .retrieval import VectorDatabase,Hit
from .augment import augment_user_prompt
from .generation import generate_answer

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = ("This feels like something Future Me would yell at Present Me for agreeing to."
                     "Provide more context to work with.")

@dataclass(frozen=True)
class Answer:
    text: str
    source: list[Hit]


class RagPipeline:
    '''Documentation String'''
    def __init__(self,vector_db: VectorDatabase | None = None):
        settings = get_settings()
        self.vector_db = vector_db or VectorDatabase(settings.collection_name,settings.similarity_metric)
        self._write_lock = threading.Lock()

    def index_documents(self,doc_id:int,title:str,category:str,content:str) -> int:
        chunks = chunk_document(doc_id,title,category,content)
        embeddings = embed_texts([chunk.text for chunk in chunks])

        with self._write_lock:
            self.vector_db.add(chunks,embeddings)
            self.vector_db.delete(doc_id)

        return len(chunks)

    def remove_document(self,doc_id:int) -> None:
        with self._write_lock:
            self.vector_db.delete(doc_id)

    def reset(self) -> None:
        with self._write_lock:
            self.vector_db.reset()

    def retrieval(self,question:str,top_k:int | None = None,category:str | None = None) -> list[Hit]:
        settings = get_settings()
        top_results = min(top_k or settings.top_k,settings.max_top_k)
        hits = self.vector_db.retrieve(embed_query(question),top_results,category)

        return [ hit for hit in hits if hit.similarity >= settings.min_similarity ]

    def answer(self,question:str,top_k:int | None = None,category:str | None = None) -> Answer:
        hits = self.retrieval(question,top_k,category)

        if not hits:
            return Answer(NO_CONTEXT_ANSWER,[])

        return Answer(generate_answer(augment_user_prompt(question,hits)),hits)
