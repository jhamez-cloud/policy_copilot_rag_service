# Policy Copilot RAG Service

A Python 3.11 FastAPI service for querying a document collection with retrieval-augmented generation (RAG). PostgreSQL stores the source documents; an in-memory Chroma collection stores searchable chunks and is rebuilt from PostgreSQL when the service starts. Answers are generated with Google's Gemini API through the `google-genai` SDK.

## Project status

Query, health, document listing, document detail, document upload, and document deletion routes are implemented. Startup seeding from `data/policies/` is also implemented.

## Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- A PostgreSQL database (the settings and `.env.example` use Neon)
- A Google Gemini API key for generated answers
- LibreOffice for legacy `.ppt` uploads and as a fallback for some `.doc` files; `antiword` is also supported for `.doc` (Debian/Ubuntu: `sudo apt-get install antiword libreoffice-writer`)

## Quick start

Create a database and copy its connection string from your database provider. From the repository root:

```bash
cp .env.example .env
```

Set the required database URL and add the API keys in `.env`:

```dotenv
NEON_DATABASE_URL="postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
ADMIN_API_KEY="generate-a-long-random-secret"
LLM_API_KEY="your-google-genai-api-key"
```

Generate an admin key with:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Install dependencies and start the API from the repository root:

```bash
uv sync
uv run policy-copilot-rag-service
```

The service listens on `0.0.0.0:8000` by default. Use `uv run policy-copilot-rag-service --host 127.0.0.1 --port 8000 --reload` for local development with automatic reload. Interactive API documentation is at <http://127.0.0.1:8000/docs>.

At startup the service creates database tables if needed, optionally seeds Markdown files from `data/policies/`, loads the embedding model, clears the in-memory vector collection, and indexes every document from PostgreSQL. The first run may download the embedding model. Keep a working network connection until that download completes.

Run one worker only. Chroma is in memory and each process would otherwise have its own independent index. `--reload` is intended for local development.

## API

Protected endpoints require `X-API-Key: <ADMIN_API_KEY>`. If `ADMIN_API_KEY` is empty, protected operations return 503; a missing or incorrect key returns 401.

| Method | Path | Access | Behavior |
|---|---|---|---|
| `GET` | `/api/v1/` | Public | Basic running status |
| `POST` | `/api/v1/query` | Public | Retrieve context and generate an answer |
| `GET` | `/api/v1/documents` | Public | List documents; supports `limit`, `offset`, and `category` |
| `GET` | `/api/v1/documents/{doc_id}` | Public | Return document metadata and full content |
| `POST` | `/api/v1/documents/upload` | Admin | Extract and index `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.csv`, `.txt`, `.md` or `.markdown` files |
| `GET` | `/api/v1/documents/upload-options` | Public | Available file extensions and configured upload/extraction limits |
| `DELETE` | `/api/v1/documents/{doc_id}` | Admin | Delete a document and its indexed chunks |
| `GET` | `/health` | Public | Database connectivity, document count, and indexed chunk count |

### Query

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How are documents retained?","top_k":3}'
```

The request requires a question between 3 and 1000 characters. `top_k` is optional (request range 1–10); retrieval is also capped by `MAX_TOP_K`. `category` is optional and filters results to an exact category. An empty category is treated as no filter.

Successful responses contain `answer`, `sources`, and `model`. Each source includes the document ID, title, category, chunk ID, similarity, and a text excerpt. Similarities are returned rounded to three decimal places. If retrieval returns no chunks, the service returns its fixed no-context message and an empty `sources` list without calling Gemini. If generation fails, the endpoint returns 503; inspect the server log for the upstream error details.

Seed document categories are derived from their immediate parent directory under `data/policies/`, lowercased (for example, `03_privacy_and_data_protection`).

### Documents

`GET /api/v1/documents` returns `{ "total": number, "items": [...] }`. `limit` defaults to 20 and must be 1–100; `offset` defaults to 0 and must be non-negative. The optional category filter is trimmed and lowercased.

To upload through Swagger, open `POST /api/v1/documents/upload`, select **Try it out**, choose one or more files in the `files` field, enter the `X-API-Key` header value, and execute the request. The optional `category` defaults to `general`; `library_id` may be supplied to associate the uploads with a library. The endpoint accepts `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.csv`, `.txt`, `.md` and `.markdown`. It extracts readable text before normalization, title derivation, duplicate hashing, PostgreSQL storage and Chroma indexing. The original filename is retained; original binaries are not stored. Each file receives an `indexed`, `duplicate`, or `rejected` result, so a damaged file does not block other valid files.

PDF conversion uses `pypdf`, DOCX uses `python-docx`, PPTX uses `python-pptx`, and CSV uses Python's standard CSV reader. DOCX preserves paragraph/table reading order and headings. PowerPoint extraction includes slide text, grouped text, tables and speaker notes; legacy `.ppt` files are converted to `.pptx` with LibreOffice before extraction. CSV rows include their column labels; UTF-8 and BOM-marked UTF-16 text are supported. Legacy DOC conversion uses a temporary file and `antiword` without a shell, with a LibreOffice fallback in an isolated profile for short or RTF-based Word files. Office conversion has a 30-second timeout. `GET /api/v1/documents/upload-options` reports available extensions and limits; `.doc` is omitted when both `antiword` and LibreOffice are unavailable, and `.ppt` is omitted when LibreOffice is unavailable.

Scanned PDFs and image-only documents require OCR before upload. Embedded images are not extracted, and password-protected documents are rejected with a per-file explanation. PDFs are capped at 1,000 pages; Office archives at 50,000,000 expanded bytes and 5,000 entries. Extracted text defaults to a 2,000,000-character limit. Equivalent normalized text is a duplicate even when uploaded in different formats.

## Configuration

Settings are read from environment variables or `.env`. The settings implementation is in `src/policy_copilot_rag_service/settings.py`.

| Variable | Default | Notes |
|---|---|---|
| `NEON_DATABASE_URL` | Required | PostgreSQL connection URL. The application converts `postgres://` and `postgresql://` schemes to the Psycopg 3 SQLAlchemy driver. |
| `ADMIN_API_KEY` | Empty | Shared key for upload and delete routes. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Passed to the CORS middleware by the application. |
| `DATA_DIR` | `data/policies/` | Directory containing seed Markdown documents. |
| `SEED_ON_STARTUP` | `true` | Seed Markdown documents on application startup. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `400` / `100` | Markdown chunk size and overlap, in characters. |
| `EMBEDDING_MODEL` | `all-MiniLm-L6-v2` | Sentence Transformers model used for documents and queries. |
| `COLLECTION_NAME` | `policy_documents` | Chroma collection name. |
| `SIMILARITY_METRIC` | `cosine` | Chroma distance metric. |
| `TOP_K` / `MAX_TOP_K` | `3` / `6` | Default retrieval count and service-side maximum. |
| `MIN_SIMILARITY` | `0.0` | Discards retrieved chunks below this similarity. |
| `LLM_API_KEY` | Empty | Google Gemini API key used by `google-genai`. |
| `LLM_MODEL` | `gemini-3.8-flash` | Gemini model name passed to the SDK; confirm the name is available to your API key. |
| `LLM_MAX_TOKENS` | `1000` | Maximum generated output tokens. |
| `LLM_TIMEOUT_SECONDS` | `30.0` | Defined in settings, but not currently passed to the Google GenAI client. |
| `LLM_BASE_URL` | Gemini OpenAI-compatible URL | Defined in settings but not used by the active Google GenAI client. Changing it does not switch providers. |
| `MAX_UPLOAD_BYTES` / `MAX_FILES_PER_UPLOAD` | `20000000` / `10` | Maximum original file bytes and files per multipart request; environment overrides apply. |
| `MAX_EXTRACTED_CHARS` | `2000000` | Maximum readable text characters per document before indexing. |
| `LOG_LEVEL` | `INFO` | Logging level configured at startup. |

The active generation client is Google Gemini. Although `LLM_BASE_URL` exists in settings, the implementation does not currently support switching to OpenAI-compatible providers by changing environment variables alone.

Changing chunking or embedding settings requires a restart. Startup rebuilds the in-memory vector index from all documents stored in PostgreSQL.

## Data and implementation

- `data/policies/` contains the Markdown seed corpus. Subdirectory names become document categories.
- PostgreSQL is the durable source of truth for full document text and metadata.
- Chroma stores embedded chunks in process memory; it is derived data and is rebuilt at every startup.
- The embedding model is loaded once per process and is used for both document chunks and query text.
- Database tables are created with SQLAlchemy `create_all`; no migration system is currently configured.

Main code areas:

```text
src/policy_copilot_rag_service/
  settings.py
  api/             FastAPI app, routes, schemas, database, and ingestion service
  rag/             chunking, embeddings, retrieval, prompt assembly, generation
```

## Development checks

Install the project's dependencies, including the development dependency group:

```bash
uv sync
```

Run the offline storage, ingestion, retrieval and API tests from `src/policy_copilot_rag_service`:

```bash
../../.venv/bin/python -m pytest tests api/db/tests rag/tests -q
```

`tests/test_document_formats.py` exercises real PDF, DOCX, DOC, PPTX and CSV conversion, mixed multipart uploads, citations, cross-format deduplication, invalid/encrypted files and extraction limits. The legacy DOC fixture was generated with LibreOffice and is converted using `antiword`.

## Troubleshooting

| Symptom | Check |
|---|---|
| Settings validation says `neon_database_url` is missing | Create `.env` in the directory where you run the service and set `NEON_DATABASE_URL`. |
| PostgreSQL connection or SSL error | Verify the database URL, credentials, network access, and provider-required SSL parameters such as `sslmode=require`. |
| First startup fails while downloading the embedding model | Check network stability and retry; the model must be available locally before indexing can complete. |
| Admin operation returns 503 | Set a non-empty `ADMIN_API_KEY` and restart the service. |
| Query returns the no-context fallback | Check that the index has chunks, the category matches exactly, and `MIN_SIMILARITY` is not excluding results. |
| Query endpoint returns 503 | Check `LLM_API_KEY`, the configured Gemini model name, API access/quota, and the detailed `LLM call failed` server log. |
| Chroma logs telemetry capture errors | These are telemetry integration errors; they are separate from retrieval and generation failures. |
