# Project structure and request flows

Policy Copilot is a Python 3.11 FastAPI service for answering questions about uploaded documents and the software's policies. Neon/PostgreSQL stores documents, libraries, and sessions. A shared Chroma collection holds embedded document chunks in process memory. Google's Gemini API generates answers from retrieved excerpts.

## Repository and package map

Paths below are relative to the repository root unless shown inside the package tree.

| Root path | Purpose |
| --- | --- |
| `pyproject.toml` | Python requirement, dependency groups, build backend, console entry point, and CPU PyTorch indexes. |
| `uv.lock`, `.python-version` | Resolved dependencies and the Python 3.11 runtime selection. |
| `.env.example` | Database URL setting name; other settings are defined in `settings.py`. |
| `README.md`, `docs/ARCHITECTURE.md` | Original setup and architecture documentation; some descriptions predate library/session support. |
| `data/policies/` | 28 Markdown seed documents across platform, legal, privacy, AI/RAG, intellectual property, security, and support/governance categories. |
| `src/policy_copilot_rag_service/` | Installable application package, tests, and this guide. |

```text
src/policy_copilot_rag_service/
├── __init__.py                 console script's greeting function
├── settings.py                 cached environment-based Settings
├── api/
│   ├── main.py                 app factory, router registration, lifespan
│   ├── dependencies.py         shared pipeline and admin-key dependencies
│   ├── schemas.py              Pydantic request/response models
│   ├── routes/
│   │   ├── health.py           database and index health
│   │   ├── document.py         upload, list, detail, delete
│   │   ├── library.py          library CRUD and document membership
│   │   ├── session.py          persistent session/library selection
│   │   └── query.py            resolve SQL scopes and request an answer
│   ├── services/ingestion.py   validation, hashing, seeding, index rebuild
│   └── db/
│       ├── models.py           Document, Library, ChatSession ORM models
│       ├── repository.py       SQL reads/writes; callers commit transactions
│       ├── session.py          engine, connection pool, schema initialization
│       ├── migrations.py       additive document/library schema upgrades
│       └── tests/              schema upgrade and library deletion checks
├── rag/
│   ├── chunking.py             Markdown splitting and chunk metadata
│   ├── embeddings.py           Sentence Transformer model and encoding
│   ├── retrieval.py            Chroma operations and document-ID filters
│   ├── augment.py              excerpts, provenance labels, system prompt
│   ├── generation.py           Gemini client and GenerationError
│   ├── pipeline.py             indexing, retrieval, and answer orchestration
│   └── tests/                  retrieval and prompt regression tests
├── tests/                      API, ingestion, and integration fixtures
└── docs/                       project guide and library/session API guide
```

`api/` owns HTTP and SQL integration. `rag/` uses the shared settings but does not import the API or database layer. The query router supplies document-ID lists to the pipeline; ingestion connects durable documents to their derived vectors.

## Dependencies

These constraints are copied from [pyproject.toml](../../../pyproject.toml); they are declared requirements, not installed-version snapshots. Python is `>=3.11,<3.12`.

| Requirement | Role |
| --- | --- |
| `chromadb==0.4.22` | In-memory vector storage and similarity search. |
| `fastapi>=0.162.0` | HTTP application, routing, validation, and dependency injection. |
| `google-genai>=3.0.0` | Active Gemini generation client. |
| `huggingface-hub>=0.26,<0.32` | Embedding model download/cache support. |
| `langchain==0.1.0` | Markdown-aware recursive text splitter. |
| `numpy>=1.26.0,<2` | Numerical support for embeddings and Chroma. |
| `openai>=3.45.0` | Declared SDK; the active generator uses `google-genai`. |
| `psycopg[binary]>=3.3.8` | PostgreSQL driver. |
| `pydantic-settings>=2.16.2` | Environment and local configuration loading. |
| `python-multipart>=0.0.33` | Multipart document uploads. |
| `sentence-transformers>=3.0,<4.0` | Document and query embeddings. |
| `sqlalchemy>=2.1.8` | ORM, database sessions, and schema operations. |
| `torch>=2.15.0` | Embedding inference runtime. |
| `torchvision>=0.29.2` | Declared PyTorch companion dependency. |
| `uvicorn[standard]>=0.54.0` | ASGI server. |
| `httpx>=0.28.1` | Development dependency for HTTP tests. |
| `pytest>=9.1.1` | Development test runner. |
| `uv_build>=0.13.6,<0.14.0` | Build-system dependency and backend. |

Pydantic supplies API schemas through the FastAPI/settings dependency stack. The `uv` configuration selects CPU-index wheels for `torch` and `torchvision` on Linux and Windows.

## Database and library/session design

| Model / table | Stored information and relationships |
| --- | --- |
| `Document` / `documents` | ID, title, category, filename, full text, unique SHA-256 content hash, source, chunk count, creation time, nullable indexed `library_id`. |
| `Library` / `libraries` | ID, name, creation time, nullable unique internal `system_key`, and ORM relationships to documents/sessions. API metadata exposes derived `is_system`; document membership uses `documents.library_id`. |
| `ChatSession` / `sessions` | ID, creation time, and nullable indexed `library_id`. A session persists a selected library; this model does not store a conversation transcript. |

A document belongs to at most one library. Adding an existing document to another library moves its membership. Removing membership sets `library_id` to `NULL`, which represents uncategorized documents independently of their `category` value.

Both document and session foreign keys use `ON DELETE SET NULL`. Deleting a user library preserves its documents and sessions; the documents become uncategorized, and surviving sessions can select a new library. Software policies are identified by `source == "seed"`, belong to the built-in **Software policy** library, and remain globally searchable in every query. The built-in library and its documents reject all admin mutations with 403, including moves or permanent deletion through global document endpoints. Ordinary user libraries remain editable.

`init_db()` creates missing tables, then runs the idempotent upgrade in `api/db/migrations.py` to add the document-library foreign key/index and unique nullable library system key to older schemas. It creates the built-in library and attaches all previously seeded documents in the same transaction, even when directory seeding is disabled. Existing document IDs, content, categories, and uploaded-document memberships are preserved. PostgreSQL schema initialization uses a transaction advisory lock; SQLite connections enable foreign keys. The project has no Alembic configuration or revision history.

## API surface and services

All application routes below use `/api/v1`; `/health` is outside that prefix. Interactive OpenAPI documentation is at `/docs`.

| Method | Path | Behavior / access |
| --- | --- | --- |
| `GET` | `/api/v1/` | Running status; public. |
| `POST` | `/api/v1/query` | Question, optional `top_k`, `category`, `session_id`; public. |
| `GET` | `/api/v1/documents` | Paginated list; optional category and `library_id` or `uncategorized`; public. |
| `GET` | `/api/v1/documents/{doc_id}` | Metadata and full document text; public. |
| `POST` | `/api/v1/documents/upload` | Multipart files, category, optional `library_id`; admin. |
| `DELETE` | `/api/v1/documents/{doc_id}` | Delete the document and its indexed chunks; admin. |
| `GET`, `POST` | `/api/v1/libraries` | List publicly; create with an admin key. |
| `GET`, `PATCH`, `DELETE` | `/api/v1/libraries/{library_id}` | Read publicly; rename/delete with an admin key. |
| `GET`, `POST`, `DELETE` | `/api/v1/libraries/{library_id}/documents` | List publicly; add/move or remove a batch with an admin key. |
| `DELETE` | `/api/v1/libraries/{library_id}/documents/{doc_id}` | Remove one membership while preserving the document; admin. |
| `GET`, `POST` | `/api/v1/sessions` | List sessions or create one for an existing library; public. |
| `GET`, `PATCH`, `DELETE` | `/api/v1/sessions/{session_id}` | Read, choose another existing library, or delete a session; public. |
| `GET` | `/health` | Database connectivity, document count, indexed chunk count; public. |

`get_pipeline()` returns the startup-created pipeline from `app.state`; `get_db()` provides a per-request SQLAlchemy session. `require_admin()` checks the `X-API-Key` header against `ADMIN_API_KEY` in constant time. Public library/session IDs provide retrieval organization; the application currently has no per-user authentication or ownership checks.

`services/ingestion.py` validates files (`prepare`), handles upload transactions (`ingest_file`), removes documents (`delete_document`), seeds policy text (`seed_from_directory`), and rebuilds Chroma (`rebuild_index`). Library/session routes use repository operations directly because changing membership or selection does not change document embeddings.

## Startup and indexing

1. `api/main.py` loads settings and initializes the SQL schema, including upgrades and the built-in Software policy library. Existing seeded documents are assigned to that library.
2. A `RagPipeline` creates its Chroma collection. If `SEED_ON_STARTUP` is enabled, ingestion reads sorted `DATA_DIR/**/*.md`, validates the text, and inserts new hashes with `source="seed"` into the built-in library. The immediate parent directory supplies the category. Matching existing content is marked as a seed and moved into the built-in library, including content uploaded earlier. Repeated runs use the same stable library ID; a missing directory still leaves the library available.
3. The cached Sentence Transformer model is loaded once per process.
4. `rebuild_index()` resets Chroma and indexes every SQL document, preserving its source marker and writing the resulting chunk count back to SQL.
5. The pipeline is stored on `app.state.pipeline`, then requests are accepted. Shutdown disposes the SQL engine.

Indexing splits Markdown into overlapping character-based chunks, embeds all chunk text, and replaces that document's Chroma entries under a write lock. Chunk IDs follow `doc{document_id}_chunk_{n}`; metadata includes `doc_id`, title, category, chunk index, and source. Document and question text use the same embedding model.

## Upload and document changes

The upload route validates category syntax, file count, and the optional library. Each file is read with the byte limit plus one byte to detect oversize content. Ingestion accepts `.md`, `.markdown`, and `.txt`, decodes UTF-8 with optional BOM, normalizes CRLF, rejects empty text, derives a title, and hashes normalized content.

For new content, ingestion flushes a SQL row, indexes the document, records its chunk count, then commits. Indexing failures roll back the row and remove partial vectors. Existing content produces a duplicate result without moving its library membership. The response reports each file as indexed, duplicate, or rejected.

Document deletion commits the SQL deletion before removing Chroma chunks. Library membership changes preserve content and vectors; the next query resolves the current SQL document scope. Policy seeding does not remove previous policy versions, and version/status headings remain document text rather than structured publication controls.

## Query and retrieval flow

The query router resolves both ID lists from SQL on every request:

| Request state | Uploaded-document scope | Software-policy scope |
| --- | --- | --- |
| Session with an existing library | That library's documents where `source != "seed"`. | All documents where `source == "seed"`. |
| No `session_id` | Uncategorized documents where `library_id IS NULL` and `source != "seed"`. | All seed documents. |
| Surviving session whose library was deleted | Empty document-ID list. | All seed documents. |

An unknown session returns 404. Explicit empty ID lists produce no candidates; direct pipeline callers should pass both lists, because `document_ids=None` retains the older unrestricted search behavior.

1. Clean and embed the question once.
2. Search the uploaded-document IDs, intersecting with `category` when supplied.
3. Independently search policy IDs across all policy categories.
4. Use `min(requested top_k or TOP_K, MAX_TOP_K)` for each corpus. Merge by similarity, deduplicate chunk IDs, and discard hits below `MIN_SIMILARITY`. A response can contain up to twice the capped per-corpus count. With the default cosine metric, similarity is `1 - distance`.
5. If no hits remain, return the no-context answer without calling Gemini. Otherwise assemble numbered excerpts labelled as uploaded documents or software policies and generate a grounded answer.
6. Return answer, model, selected session/library IDs, and sources containing document/chunk IDs, title, category, source marker, similarity, and excerpt. Generation failures return 503; provider timeouts return 504.

## Running and validation

From the repository root, configure the database and API settings locally, then:

```bash
uv sync
uv run uvicorn policy_copilot_rag_service.api.main:app --reload
```

Use one worker: Chroma is process-local, and uploads do not synchronize separate workers or replicas. Startup re-embeds all SQL documents. The console script named `policy-copilot-rag-service` currently prints a greeting; the Uvicorn command starts the API. No Docker, CI, or deployment manifest is configured in the repository.

Settings load environment variables and `.env` from the backend repository root. Important setting groups are `NEON_DATABASE_URL`, `ADMIN_API_KEY`, `DATA_DIR`/`SEED_ON_STARTUP`, chunking and embedding settings, retrieval limits, upload limits, and `LLM_*`. Generation uses `google-genai`; `LLM_TIMEOUT_SECONDS` defaults to 60 seconds and is converted to SDK milliseconds with automatic retries disabled. The OpenAI-compatible base URL is not used by that client. Ship the external `data/policies/` corpus with a deployment or set `DATA_DIR` explicitly; it is outside the package's default wheel source tree.

Tests live under package-local `tests/`, `rag/tests/`, and `api/db/tests/`. API fixtures use SQLite with foreign keys, real Chroma, deterministic embeddings, and a fake generator. From the repository root, collect and run package tests with:

```bash
uv run pytest src/policy_copilot_rag_service
```

For request bodies and API examples, see [Libraries and sessions](LIBRARIES_AND_SESSIONS.md).
