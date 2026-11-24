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

NO_CONTEXT_ANSWER = (
    "I couldn't find relevant information in the selected library or software policies. "
    "Try a more specific question or add relevant documents to the library."
)

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

    def index_documents(
        self,
        doc_id: int,
        title: str,
        category: str,
        content: str,
        *,
        source: str = "upload",
    ) -> int:
        chunks = chunk_document(doc_id,title,category,content,source=source)
        embeddings = embed_texts([chunk.text for chunk in chunks])

        with self._write_lock:
            self.vector_db.delete(doc_id)
            self.vector_db.add(chunks,embeddings)

        return len(chunks)

    def remove_document(self,doc_id:int) -> None:
        with self._write_lock:
            self.vector_db.delete(doc_id)

    def reset(self) -> None:
        with self._write_lock:
            self.vector_db.reset()

    def retrieval(
        self,
        question: str,
        top_k: int | None = None,
        category: str | None = None,
        *,
        document_ids: list[int] | None = None,
        policy_document_ids: list[int] | None = None,
    ) -> list[Hit]:
        """Retrieve up to top_k hits per corpus, capped by settings.max_top_k.

        Library hits use document_ids and the optional category filter. Policies
        use policy_document_ids independently and ignore the category filter.
        Both searches share one question embedding. Results are ranked and
        deduplicated by chunk ID, then filtered by settings.min_similarity.
        Both corpora can contribute up to 2 * top_k sources in total; there is
        no shared top_k truncation that could crowd out relevant policies.

        With document_ids=None, the first search retains its legacy unscoped
        behavior. With policy_document_ids=None, no separate policy search runs.
        Pass explicit ID lists, including [], to scope both corpora.
        """
        settings = get_settings()
        top_results = min(top_k or settings.top_k,settings.max_top_k)
        embedding = embed_query(question)
        hits = self.vector_db.retrieve(
            embedding,top_results,category,document_ids=document_ids,
        )
        if policy_document_ids is not None:
            hits = hits + self.vector_db.retrieve(
                embedding,top_results,document_ids=policy_document_ids,
            )

        ranked_hits = sorted(hits,key=lambda hit: hit.similarity,reverse=True)
        unique_hits: dict[str, Hit] = {}
        for hit in ranked_hits:
            if hit.similarity >= settings.min_similarity:
                unique_hits.setdefault(hit.chunk_id,hit)
        return list(unique_hits.values())

    def answer(
        self,
        question: str,
        top_k: int | None = None,
        category: str | None = None,
        *,
        document_ids: list[int] | None = None,
        policy_document_ids: list[int] | None = None,
    ) -> Answer:
        """Answer from scoped excerpts, with top_k sources allowed per corpus."""
        hits = self.retrieval(
            question,top_k,category,
            document_ids=document_ids,policy_document_ids=policy_document_ids,
        )

        if not hits:
            return Answer(NO_CONTEXT_ANSWER,[])

        return Answer(generate_answer(augment_user_prompt(question,hits)),hits)
