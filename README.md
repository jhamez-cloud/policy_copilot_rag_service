# Policy RAG API

A FastAPI backend that answers employee questions about company policies using Retrieval-Augmented Generation (RAG). Documents live in a **Neon Postgres** database, and new documents can be uploaded through the API and become searchable immediately.

- **Ask:** `POST /api/v1/query` retrieves the most relevant policy chunks and has an LLM answer from them, with sources.
- **Grow the dataset:** `POST /api/v1/documents/upload` stores `.md` / `.txt` files in Postgres and indexes them.
- **Manage:** list, read and delete documents.

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Project structure, how the RAG pipeline is integrated, every workflow step by step |
| [docs/PACKAGES.md](docs/PACKAGES.md) | Every dependency, what it's for, and where it's used |

## Quick start

### 1. Create the Neon database

1. Create a project at [neon.tech](https://neon.tech).
2. Open **Connect** in the dashboard and copy the connection string.

Tables are created automatically on first startup. There's no manual schema step.

### 2. Configure

```bash
cp .env.example .env
```

Fill in at least these three values:

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Neon connection string (`postgresql://...?sslmode=require`) |
| `ADMIN_API_KEY` | Secret for upload/delete. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `LLM_API_KEY` | Key for your LLM provider (see [LLM providers](#llm-providers)) |

### 3. Install and run

```bash
uv sync
uv run uvicorn policy_rag.api.main:app --reload
```

Open **http://localhost:8000/docs** for interactive API docs.

On startup the app creates tables, loads the sample files from `data/policies/` into Postgres (skipping any it already has), and builds the vector index. The first start downloads the embedding model (~90 MB).

> **Run a single worker.** The vector index lives in each process's memory, so `--workers 2+` would give inconsistent search results. See [limitations](docs/ARCHITECTURE.md#9-limitations-and-scaling-path).

## API

Base path: `/api/v1`. Auth for protected endpoints is the header `X-API-Key: <ADMIN_API_KEY>`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/query` | none | Ask a question |
| `POST` | `/documents/upload` | admin | Upload one or more `.md`/`.txt` files |
| `GET` | `/documents` | none | List documents (`limit`, `offset`, `category`) |
| `GET` | `/documents/{id}` | none | One document with full text |
| `DELETE` | `/documents/{id}` | admin | Remove from Postgres and the index |
| `GET` | `/health` (no prefix) | none | DB connectivity and index size |

### Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How much can I claim for a standing desk?"}'
```

```json
{
  "answer": "Per the Remote Work Furniture Policy, up to $300 per item with manager approval...",
  "sources": [
    {
      "document_id": 2,
      "title": "Remote Work Furniture Policy",
      "category": "reimbursement",
      "chunk_id": "doc2_chunk_0",
      "similarity": 0.6123,
      "excerpt": "# Remote Work Furniture Policy ..."
    }
  ],
  "model": "gemini-2.5-flash"
}
```

Optional body fields: `top_k` (1 to 10) and `category` (search only that category).

### Upload documents

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "X-API-Key: $ADMIN_API_KEY" \
  -F "category=hr" \
  -F "files=@./parental-leave.md" \
  -F "files=@./code-of-conduct.md"
```

```json
{
  "indexed": 1,
  "skipped": 1,
  "results": [
    {"filename": "parental-leave.md", "status": "indexed", "detail": "",
     "document": {"id": 6, "title": "Parental Leave", "category": "hr", "chunk_count": 4, "...": "..."}},
    {"filename": "code-of-conduct.md", "status": "duplicate", "detail": "Same content as document 3", "document": {"...": "..."}}
  ]
}
```

Rules:

- Allowed types: `.md`, `.markdown`, `.txt` (UTF-8). Max 1 MB per file, 10 files per request (configurable).
- `category`: lowercase letters, digits, `-`, `_` (default `general`).
- Title comes from the first `# Heading`, otherwise from the filename.
- Identical content is detected by hash and skipped as `duplicate`.
- Each file gets its own `status`: `indexed`, `duplicate` or `rejected`. The request returns **201** if at least one file was indexed, otherwise **200**.

## Configuration

Everything is an environment variable (or a line in `.env`). Defaults are in `src/policy_rag/settings.py`.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | *required* | Neon connection string |
| `ADMIN_API_KEY` | empty | Empty disables upload/delete (503) |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed frontends |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `150` | Characters per chunk / shared between chunks |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `TOP_K` / `MAX_TOP_K` | `3` / `10` | Default and maximum chunks retrieved |
| `MIN_SIMILARITY` | `0.0` | Drop chunks below this cosine similarity (0 = off) |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | Gemini / `gemini-2.5-flash` / empty | LLM provider |
| `MAX_UPLOAD_BYTES` / `MAX_FILES_PER_UPLOAD` | `1000000` / `10` | Upload limits |
| `SEED_ON_STARTUP` | `true` | Load `data/policies/` at startup |
| `LOG_LEVEL` | `INFO` | Python logging level |

If you change `CHUNK_SIZE`, `CHUNK_OVERLAP` or `EMBEDDING_MODEL`, restart the app. The index is rebuilt at startup, so the change applies to all documents.

### LLM providers

Any OpenAI-compatible endpoint works. Change three variables:

| Provider | `LLM_BASE_URL` | `LLM_MODEL` (example) |
|---|---|---|
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | any `:free` model |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.2:3b` (key can be any value) |

Model names change often, so check the provider's docs for current ones.

## Tests

```bash
uv sync                # installs the dev group (pytest, httpx)
uv run pytest
```

The tests use SQLite, fake embeddings and a fake LLM, so they need no Neon connection, model download or API key. They cover auth, upload, duplicate handling, validation, search, filtering and delete.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ValidationError: database_url Field required` at startup | `.env` missing or not in the directory you run from |
| `OperationalError: ... SSL` / connection refused | Keep `?sslmode=require` in the Neon URL |
| First request after idle is slow or fails once | Neon scales idle compute to zero; it wakes within a second or two. The pool pre-pings, so retry |
| `503 ADMIN_API_KEY is not configured` | Set `ADMIN_API_KEY` in `.env` |
| `502 The language model is unavailable` | Check `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and the provider's rate limit. Details are in the server log |
| Answer says nothing was found | The index is empty, the category filter matched nothing, or `MIN_SIMILARITY` is too high |
| `operator torchvision::nms does not exist` | torch/torchvision mismatch. Add both as direct dependencies with the CPU index (see `pyproject.toml`) |
