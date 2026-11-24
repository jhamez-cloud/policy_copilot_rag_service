'''Documentation String'''
import chromadb
from dataclasses import dataclass
from .chunking import Chunk

@dataclass(frozen=True)
class Hit:
    chunk_id: str
    doc_id: int
    title: str
    category: str
    text: str
    similarity: float
    source: str = "upload"


class VectorDatabase:
    '''Documentation String'''
    def __init__(self,collection_name:str,metric:str = "cosine"):
        self._client = chromadb.Client()
        self._name = collection_name
        self._metric = metric
        self._collection = self._create()

    def _create(self):
        return self._client.get_or_create_collection(
            name=self._name,
            metadata={
                "hnsw:space":self._metric
            }
        )

    def reset(self):
        try:
            self._client.delete_collection(self._name)
        except Exception:
            pass

        self._collection = self._create()

    def add(self, chunks: list[Chunk], embeddings:list[list[float]]) -> None:
        if not chunks:
            return

        # for chunk in chunks:
        #     self._collection.add(
        #         ids = [chunk.id],
        #         documents = [chunk.text],
        #         metadatas = [chunk.metadata],
        #         embeddings = embeddings
        #     )

        self._collection.add(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            embeddings=embeddings
        )

    def delete(self,doc_id:int) -> None:
        self._collection.delete(where={"doc_id":doc_id})

    def count(self) -> int:
        return self._collection.count()

    def retrieve(
        self,
        embedding: list[float],
        top_k: int,
        category: str | None = None,
        *,
        document_ids: list[int] | None = None,
    ) -> list[Hit]:
        """Retrieve within the supplied document IDs; None keeps legacy scope.

        An explicit empty list has no searchable documents and never queries
        Chroma. A category filter intersects the document scope when supplied.
        """
        if top_k <= 0 or (document_ids is not None and not document_ids):
            return []

        filters = []
        if document_ids is not None:
            filters.append({"doc_id": {"$in": document_ids}})
        if category:
            filters.append({"category": category})

        where = None
        if len(filters) == 1:
            where = filters[0]
        elif filters:
            where = {"$and": filters}

        if where:
            searchable = len(self._collection.get(where=where, include=[])["ids"])
        else:
            searchable = self.count()

        if searchable == 0:
            return []

        kwargs = {"query_embeddings":[embedding],"n_results": min(top_k,searchable)}
        if where:
            kwargs["where"] = where

        query_result = self._collection.query(**kwargs)

        return [Hit(
            chunk_id=chunk_id,
            doc_id=int(metadata["doc_id"]),
            title=metadata["title"],
            category=metadata["category"],
            text=text,
            similarity=1-distance,
            source=metadata.get("source", "upload"),
        ) for chunk_id,distance,text,metadata in zip(
            query_result["ids"][0],
            query_result["distances"][0],
            query_result["documents"][0],
            query_result["metadatas"][0]
        )]
