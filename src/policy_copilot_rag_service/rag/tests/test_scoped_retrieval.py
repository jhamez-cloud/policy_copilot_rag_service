"""Scoped RAG checks using in-memory Chroma and deterministic fake embeddings."""
from types import SimpleNamespace
from unittest.mock import Mock, call
from uuid import uuid4

import chromadb
import pytest
from chromadb.config import Settings as ChromaSettings

from policy_copilot_rag_service.rag import chunking, pipeline as pipeline_module
from policy_copilot_rag_service.rag.augment import augment_user_prompt
from policy_copilot_rag_service.rag.chunking import Chunk, chunk_document
from policy_copilot_rag_service.rag.pipeline import NO_CONTEXT_ANSWER, RagPipeline
from policy_copilot_rag_service.rag.retrieval import Hit, VectorDatabase


@pytest.fixture
def rag_settings(monkeypatch):
    # Never instantiate application settings or read a .env file in these tests.
    settings = SimpleNamespace(
        top_k=2, max_top_k=6, min_similarity=0.0,
        chunk_size=400, chunk_overlap=100,
    )
    monkeypatch.setattr(pipeline_module, "get_settings", lambda: settings)
    monkeypatch.setattr(chunking, "get_settings", lambda: settings)
    chunking._get_splitter.cache_clear()
    yield settings
    chunking._get_splitter.cache_clear()


@pytest.fixture
def vector_db():
    client = chromadb.EphemeralClient(
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    name = f"scoped-rag-{uuid4().hex}"
    db = VectorDatabase.__new__(VectorDatabase)
    db._collection = client.create_collection(
        name=name, metadata={"hnsw:space": "cosine"}, embedding_function=None,
    )
    yield db
    client.delete_collection(name)


@pytest.fixture
def corpus_db(vector_db):
    documents = [
        (1, "Library A report", "reports", "upload", [1.0, 0.0]),
        (2, "Library B report", "reports", "upload", [1.0, 0.0]),
        (3, "Library A contract", "legal", "upload", [0.9, 0.1]),
        (10, "Software privacy policy", "privacy", "seed", [0.8, 0.6]),
        (11, "Software availability policy", "availability", "seed", [0.6, 0.8]),
    ]
    chunks = [
        Chunk(
            f"doc{doc_id}_chunk_1", f"Excerpt from {title}.",
            {"doc_id": doc_id, "title": title, "category": category, "source": source},
        )
        for doc_id, title, category, source, _ in documents
    ]
    vector_db.add(chunks, [embedding for *_, embedding in documents])
    return vector_db


@pytest.fixture
def query_embedding(monkeypatch):
    embed = Mock(return_value=[1.0, 0.0])
    monkeypatch.setattr(pipeline_module, "embed_query", embed)
    return embed


@pytest.fixture
def pipeline(corpus_db, rag_settings, query_embedding):
    return RagPipeline(corpus_db)


@pytest.mark.parametrize("category", [None, "reports"])
def test_empty_scope_never_accesses_chroma(category):
    db = VectorDatabase.__new__(VectorDatabase)
    db._collection = Mock()

    assert db.retrieve([1.0, 0.0], 3, category, document_ids=[]) == []
    assert db._collection.mock_calls == []


@pytest.mark.parametrize(
    ("document_ids", "category", "expected_ids"),
    [
        ([1, 3], None, {1, 3}),
        ([1, 3], "reports", {1}),
        ([1, 3], "privacy", set()),
        ([999], None, set()),
        (None, "reports", {1, 2}),
        (None, None, {1, 2, 3, 10, 11}),
    ],
)
def test_retrieval_intersects_document_scope_and_category(
    corpus_db, document_ids, category, expected_ids,
):
    hits = corpus_db.retrieve(
        [1.0, 0.0], 20, category, document_ids=document_ids,
    )
    assert {hit.doc_id for hit in hits} == expected_ids


def test_scope_changes_take_effect_without_reindexing(corpus_db):
    assert [hit.doc_id for hit in corpus_db.retrieve(
        [1.0, 0.0], 2, document_ids=[1],
    )] == [1]
    assert corpus_db.retrieve([1.0, 0.0], 2, document_ids=[]) == []
    assert [hit.doc_id for hit in corpus_db.retrieve(
        [1.0, 0.0], 2, document_ids=[2],
    )] == [2]
    assert corpus_db.count() == 5


def test_legacy_metadata_defaults_to_upload(vector_db):
    vector_db.add([
        Chunk("legacy", "Existing document", {
            "doc_id": 1, "title": "Existing document", "category": "general",
        }),
    ], [[1.0, 0.0]])
    assert vector_db.retrieve([1.0, 0.0], 1)[0].source == "upload"


def test_dual_corpora_preserve_policies_beyond_library_top_k(pipeline, query_embedding):
    hits = pipeline.retrieval(
        "What do these documents say?", 2,
        document_ids=[1, 3], policy_document_ids=[10, 11],
    )
    query_embedding.assert_called_once_with("What do these documents say?")
    assert [hit.doc_id for hit in hits] == [1, 3, 10, 11]
    assert [hit.source for hit in hits] == ["upload", "upload", "seed", "seed"]
    assert [hit.similarity for hit in hits] == sorted(
        [hit.similarity for hit in hits], reverse=True,
    )


def test_category_filters_library_but_never_policies(pipeline, query_embedding):
    hits = pipeline.retrieval(
        "What applies?", 2, "reports",
        document_ids=[1, 3], policy_document_ids=[10, 11],
    )
    assert [hit.doc_id for hit in hits] == [1, 10, 11]
    query_embedding.assert_called_once_with("What applies?")


@pytest.mark.parametrize(
    ("document_ids", "policy_document_ids", "expected_ids"),
    [([], [10], [10]), ([1], [], [1]), ([], [], []), ([1], None, [1])],
)
def test_empty_corpora_do_not_expand_scope(
    pipeline, document_ids, policy_document_ids, expected_ids,
):
    hits = pipeline.retrieval(
        "What applies?", document_ids=document_ids,
        policy_document_ids=policy_document_ids,
    )
    assert [hit.doc_id for hit in hits] == expected_ids


def test_legacy_pipeline_call_still_searches_once(pipeline, corpus_db, monkeypatch):
    retrieve = Mock(wraps=corpus_db.retrieve)
    monkeypatch.setattr(corpus_db, "retrieve", retrieve)

    assert {hit.doc_id for hit in pipeline.retrieval("Report?", 2, "reports")} == {1, 2}
    retrieve.assert_called_once_with([1.0, 0.0], 2, "reports", document_ids=None)


def test_max_top_k_is_applied_to_each_corpus(pipeline, rag_settings):
    rag_settings.max_top_k = 1
    hits = pipeline.retrieval(
        "What applies?", 100, document_ids=[1, 3], policy_document_ids=[10, 11],
    )
    assert [hit.doc_id for hit in hits] == [1, 10]


def test_merge_retains_best_duplicate_and_inclusive_similarity_threshold(
    rag_settings, query_embedding,
):
    rag_settings.min_similarity = 0.7
    upload = Hit("upload", 1, "Report", "reports", "Report text", 0.99)
    duplicate = Hit("policy", 10, "Policy", "privacy", "Policy text", 0.8, "seed")
    best_duplicate = Hit("policy", 10, "Policy", "privacy", "Policy text", 0.95, "seed")
    borderline = Hit("borderline", 11, "Policy 2", "legal", "More text", 0.7, "seed")
    irrelevant = Hit("irrelevant", 2, "Other", "reports", "Other text", 0.69)
    db = Mock(spec=VectorDatabase)
    db.retrieve.side_effect = [
        [duplicate, irrelevant, upload], [borderline, best_duplicate],
    ]

    hits = RagPipeline(db).retrieval(
        "Question", 3, "reports", document_ids=[1, 2, 10], policy_document_ids=[10, 11],
    )
    assert hits == [upload, best_duplicate, borderline]
    assert db.retrieve.call_args_list == [
        call([1.0, 0.0], 3, "reports", document_ids=[1, 2, 10]),
        call([1.0, 0.0], 3, document_ids=[10, 11]),
    ]
    query_embedding.assert_called_once_with("Question")


def test_answer_forwards_scope_and_labels_both_corpora(pipeline, monkeypatch):
    generate = Mock(return_value="An answer grounded in both sources.")
    monkeypatch.setattr(pipeline_module, "generate_answer", generate)

    result = pipeline.answer(
        "What applies?", 2, "reports", document_ids=[1], policy_document_ids=[10],
    )
    assert result.text == "An answer grounded in both sources."
    assert [hit.doc_id for hit in result.source] == [1, 10]
    prompt = generate.call_args.args[0]
    assert "Library A report" in prompt
    assert "Source type: Uploaded document" in prompt
    assert "Software privacy policy" in prompt
    assert "Source type: Software policy" in prompt
    assert "Library B report" not in prompt
    assert "QUESTION:\nWhat applies?" in prompt
    generate.assert_called_once()


def test_no_context_returns_helpful_message_without_generation(pipeline, monkeypatch):
    generate = Mock()
    monkeypatch.setattr(pipeline_module, "generate_answer", generate)

    result = pipeline.answer("Question", document_ids=[], policy_document_ids=[])
    assert result.text == NO_CONTEXT_ANSWER
    assert result.source == []
    generate.assert_not_called()


@pytest.mark.parametrize("source", ["upload", "seed"])
def test_reindex_replaces_old_chunks_and_preserves_source(vector_db, rag_settings, monkeypatch, source):
    monkeypatch.setattr(
        pipeline_module, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts],
    )
    rag = RagPipeline(vector_db)
    rag.index_documents(42, "Original", "general", "Original text. " * 80)
    assert vector_db.count() > 1

    assert rag.index_documents(42, "Replacement", "general", "Replacement text.", source=source) == 1
    hits = vector_db.retrieve([1.0, 0.0], 20, document_ids=[42])
    assert len(hits) == vector_db.count() == 1
    assert hits[0].text == "Replacement text."
    assert hits[0].title == "Replacement"
    assert hits[0].source == source


def test_chunking_and_prompt_support_legacy_positional_callers(rag_settings):
    chunk = chunk_document(1, "Uploaded report", "general", "Report excerpt.")[0]
    assert chunk.metadata["source"] == "upload"
    hit = Hit(chunk.id, 1, "Uploaded report", "general", chunk.text, 0.9)
    prompt = augment_user_prompt("What is in this report?", [hit])
    assert "Source type: Uploaded document" in prompt
    assert "Report excerpt." in prompt
