from ..settings import get_settings
from functools import lru_cache

@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def clean_query(question:str) -> str:
    return " ".join(question.split())


def embed_texts(texts:list[str], batch_size:int = 32) -> list[list[float]]:
    if not texts:
        return []

    vectors = get_embedding_model().encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False
    )

    return vectors.tolist()


def embed_query(question:str) -> list[float]:
    return embed_texts([clean_query(question)])[0]