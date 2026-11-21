"""Regression checks for additive upgrades and non-destructive library deletion."""

from types import SimpleNamespace
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from policy_copilot_rag_service.api.db import repository as repo
from policy_copilot_rag_service.api.db import session as db_session
from policy_copilot_rag_service.api.db.models import Base, ChatSession, Document, Library


@pytest.fixture
def sqlite_engine(tmp_path, monkeypatch):
    db_session.dispose_engine()
    settings = SimpleNamespace(neon_database_url=f"sqlite:///{tmp_path / 'database.db'}")
    monkeypatch.setattr(db_session, "get_settings", lambda: settings)
    engine = db_session.get_engine()
    try:
        yield engine
    finally:
        db_session.dispose_engine()


def _add_document(db, title, *, source="upload", library_id=None):
    return repo.add_doc(
        db,
        title=title,
        category="semantic_category",
        filename=f"{title}.md",
        content=f"Contents of {title}",
        content_hash=title.ljust(64, "0"),
        source=source,
        library_id=library_id,
    )


def test_legacy_sqlite_upgrade_preserves_rows_indexes_and_triggers(sqlite_engine):
    with sqlite_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE libraries (id INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.exec_driver_sql(
            "INSERT INTO libraries (id, name) VALUES (9, 'Existing library')"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(50) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                content_hash VARCHAR(64) NOT NULL UNIQUE,
                source VARCHAR(20) NOT NULL,
                chunk_count INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                legacy_marker TEXT NOT NULL DEFAULT 'preserve'
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_documents_category ON documents (category)"
        )
        connection.exec_driver_sql(
            """
            CREATE TRIGGER preserve_document_category
            BEFORE UPDATE OF category ON documents
            WHEN NEW.category != OLD.category
            BEGIN
                SELECT RAISE(ABORT, 'category cannot be changed');
            END
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO documents
                (id, title, category, filename, content, content_hash, source,
                 chunk_count, created_at, legacy_marker)
            VALUES
                (17, 'Policy', 'legal', 'policy.md', 'Original policy', ?,
                 'seed', 3, '2025-01-01 12:30:00', 'policy-marker'),
                (42, 'Upload', 'research', 'upload.md', 'Original upload', ?,
                 'upload', 8, '2025-02-02 12:30:00', 'upload-marker')
            """,
            ("a" * 64, "b" * 64),
        )
        original_rows = connection.exec_driver_sql(
            "SELECT * FROM documents ORDER BY id"
        ).all()
        original_rootpage = connection.exec_driver_sql(
            "SELECT rootpage FROM sqlite_master WHERE type='table' AND name='documents'"
        ).scalar_one()

    db_session.init_db()
    db_session.init_db()

    inspector = inspect(sqlite_engine)
    assert set(inspector.get_table_names()) == {"documents", "libraries", "sessions"}
    columns = {column["name"]: column for column in inspector.get_columns("documents")}
    assert columns["library_id"]["nullable"] is True
    assert "legacy_marker" in columns
    library_columns = {column["name"]: column for column in inspector.get_columns("libraries")}
    assert library_columns["system_key"]["nullable"] is True
    assert any(
        index["column_names"] == ["system_key"] and index["unique"]
        for index in inspector.get_indexes("libraries")
    )
    indexes = {index["name"]: index for index in inspector.get_indexes("documents")}
    assert indexes["ix_documents_library_id"]["column_names"] == ["library_id"]
    assert indexes["ix_documents_category"]["column_names"] == ["category"]
    foreign_keys = inspector.get_foreign_keys("documents")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["constrained_columns"] == ["library_id"]
    assert foreign_keys[0]["referred_table"] == "libraries"

    with sqlite_engine.connect() as connection:
        foreign_key = connection.exec_driver_sql(
            "PRAGMA foreign_key_list(documents)"
        ).mappings().one()
        assert foreign_key["table"] == "libraries"
        assert foreign_key["from"] == "library_id"
        assert foreign_key["to"] == "id"
        assert foreign_key["on_delete"] == "SET NULL"
        upgraded_rows = connection.exec_driver_sql(
            "SELECT * FROM documents ORDER BY id"
        ).all()
        assert [tuple(row[:-1]) for row in upgraded_rows] == [tuple(row) for row in original_rows]
        system_id = connection.exec_driver_sql(
            "SELECT id FROM libraries WHERE system_key = 'software-policy'"
        ).scalar_one()
        assert [row[-1] for row in upgraded_rows] == [system_id, None]
        assert connection.exec_driver_sql("SELECT name FROM libraries WHERE id = 9").scalar_one() == "Existing library"
        assert connection.exec_driver_sql("SELECT count(*) FROM libraries WHERE system_key IS NOT NULL").scalar_one() == 1
        assert connection.exec_driver_sql(
            "SELECT rootpage FROM sqlite_master WHERE type='table' AND name='documents'"
        ).scalar_one() == original_rootpage
        assert connection.exec_driver_sql(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='trigger' AND name='preserve_document_category'"
        ).scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    # The upgraded schema must enforce its FK and SET NULL action, not just
    # report a constraint in introspection.
    with Session(sqlite_engine, expire_on_commit=False) as db:
        library = repo.add_library(db, "Legacy documents")
        documents = repo.get_docs_by_ids(db, [42])
        repo.assign_documents_to_library(db, library.id, documents)
        chat_session = repo.add_chat_session(db, library.id)
        db.commit()
        library_id, session_id = library.id, chat_session.id

    with sqlite_engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM libraries WHERE id = ?", (library_id,))

    with Session(sqlite_engine) as db:
        assert repo.get_doc_count(db) == 2
        assert repo.get_doc_by_id(db, 17).library_id == system_id
        assert repo.get_doc_by_id(db, 42).library_id is None
        assert repo.get_chat_session_by_id(db, session_id).library_id is None
        assert repo.get_policy_document_ids(db) == [17]
        assert repo.get_document_ids_for_library(db, None) == [42]


def test_sqlite_foreign_keys_enabled_on_pooled_and_new_connections(sqlite_engine):
    # init_db must repair a pooled connection created with enforcement disabled.
    with sqlite_engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 0

    db_session.init_db()
    with sqlite_engine.connect() as first, sqlite_engine.connect() as second:
        assert first.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert second.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    with Session(sqlite_engine) as db:
        with pytest.raises(IntegrityError):
            repo.add_chat_session(db, 999)
        db.rollback()
        with pytest.raises(IntegrityError):
            _add_document(db, "invalid-library", library_id=999)
        db.rollback()
        assert repo.get_doc_count(db) == 0
        assert repo.get_chat_sessions_list(db, 10, 0) == (0, [])


@pytest.mark.parametrize("preload", ["collections", "children", "none"])
def test_delete_library_preserves_documents_sessions_and_loaded_links(sqlite_engine, preload):
    db_session.init_db()
    with Session(sqlite_engine, expire_on_commit=False) as db:
        library = repo.add_library(db, "Delete this library")
        other_library = repo.add_library(db, "Keep this library")
        system_library = repo.ensure_system_library(db)
        document = _add_document(db, "uploaded", library_id=library.id)
        policy = _add_document(db, "seeded", source="seed", library_id=system_library.id)
        other_document = _add_document(db, "other", library_id=other_library.id)
        chat_session = repo.add_chat_session(db, library.id)
        other_session = repo.add_chat_session(db, other_library.id)
        db.commit()
        library_id = library.id
        document_ids = [document.id]
        policy_id, system_library_id = policy.id, system_library.id
        chat_session_id = chat_session.id
        other_library_id, other_document_id = other_library.id, other_document.id
        other_session_id = other_session.id

    with Session(sqlite_engine, expire_on_commit=False) as db:
        library = repo.get_library_by_id(db, library_id)
        if preload != "none":
            documents = repo.get_docs_by_ids(db, document_ids)
            chat_session = repo.get_chat_session_by_id(db, chat_session_id)
            assert all(document.library is library for document in documents)
            assert chat_session.library is library
        if preload == "collections":
            assert {document.id for document in library.documents} == set(document_ids)
            assert library.sessions == [chat_session]

        repo.delete_library(db, library)
        db.commit()

        documents = repo.get_docs_by_ids(db, document_ids)
        chat_session = repo.get_chat_session_by_id(db, chat_session_id)
        assert len(documents) == 1
        assert all(document.library_id is None for document in documents)
        assert all(document.library is None for document in documents)
        assert all(document.category == "semantic_category" for document in documents)
        assert chat_session is not None
        assert chat_session.library_id is None
        assert chat_session.library is None
        assert library.documents == []
        assert library.sessions == []
        assert repo.get_library_by_id(db, library_id) is None
        assert repo.get_doc_by_id(db, other_document_id).library_id == other_library_id
        assert repo.get_doc_by_id(db, policy_id).library_id == system_library_id
        assert repo.get_chat_session_by_id(db, other_session_id).library_id == other_library_id
        assert repo.get_doc_count(db) == 3

    with Session(sqlite_engine) as db:
        assert db.get(Document, document_ids[0]).library_id is None
        assert db.get(ChatSession, chat_session_id).library_id is None
        assert repo.get_document_ids_for_library(db, None) == [document_ids[0]]
        assert repo.get_policy_document_ids(db) == [policy_id]


def test_delete_library_rollback_restores_memberships(sqlite_engine):
    db_session.init_db()
    with Session(sqlite_engine, expire_on_commit=False) as db:
        library = repo.add_library(db, "Keep after rollback")
        document = _add_document(db, "rollback", library_id=library.id)
        chat_session = repo.add_chat_session(db, library.id)
        db.commit()
        library_id = library.id
        assert document.library is library
        assert chat_session.library is library
        assert library.documents == [document]
        assert library.sessions == [chat_session]

        repo.delete_library(db, library)
        db.flush()
        db.rollback()

        assert repo.get_library_by_id(db, library_id) is library
        assert document.library_id == library_id
        assert document.library is library
        assert chat_session.library_id == library_id
        assert chat_session.library is library


def test_concurrent_system_library_creation_uses_one_stable_identity(sqlite_engine):
    Base.metadata.create_all(sqlite_engine)
    barrier = Barrier(4)

    def bootstrap(_worker):
        with Session(sqlite_engine) as db:
            barrier.wait(timeout=10)
            library = repo.ensure_system_library(db)
            library_id = library.id
            db.commit()
            return library_id

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(bootstrap, range(4)))
    assert len(set(ids)) == 1
    with Session(sqlite_engine) as db:
        total, libraries = repo.get_libraries_list(db, 10, 0)
        assert total == 1
        assert libraries[0].is_system
        db.add(Library(name="Duplicate system library", system_key=repo.SYSTEM_LIBRARY_KEY))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_startup_creates_system_library_when_directory_seeding_is_disabled(sqlite_engine, monkeypatch, tmp_path):
    from policy_copilot_rag_service.api import main

    settings = SimpleNamespace(log_level="INFO", seed_on_startup=False, data_dir=tmp_path / "missing")
    pipeline = SimpleNamespace()
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "RagPipeline", lambda: pipeline)
    monkeypatch.setattr(main, "get_embedding_model", lambda: None)
    monkeypatch.setattr(main.ingestion, "rebuild_index", lambda _pipeline, _db: (0, 0))
    app = SimpleNamespace(state=SimpleNamespace())

    async def startup():
        async with main.lifespan(app):
            assert app.state.pipeline is pipeline

    asyncio.run(startup())
    with Session(sqlite_engine) as db:
        total, libraries = repo.get_libraries_list(db, 10, 0)
        assert total == 1
        assert libraries[0].name == "Software policy"
        assert libraries[0].is_system
        assert repo.get_doc_count(db) == 0
