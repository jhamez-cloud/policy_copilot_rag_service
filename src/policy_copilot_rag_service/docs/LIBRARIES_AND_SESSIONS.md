# Libraries and query sessions

A document belongs to at most one library. `documents.library_id` references
`libraries.id`; `NULL` means **uncategorized**. The existing `category` remains
the document's topic and is independent of its library.

Deleting a library preserves its documents, text, and indexed chunks and sets
their library links to `NULL`. Existing sessions also survive with a `NULL`
library link. Documents can subsequently be assigned to another library.

Software policy documents are identified by `source="seed"`. They are searched
for every API query regardless of library membership. Seeding also recognizes
policy content uploaded before startup and marks that existing document as a
software policy instead of creating a duplicate.

## Typical workflow

All paths below use `/api/v1`. Library and document mutations require the
existing `X-API-Key` admin header. Session and query endpoints follow the
existing public query access model.

1. `POST /libraries` with `{"name":"Research"}`. Save the returned `id`.
2. Upload multipart files to `POST /documents/upload` with optional form fields
   `library_id` and `category`. Alternatively, assign existing documents with
   `POST /libraries/{id}/documents` and `{"document_ids":[1,2]}`.
3. `POST /sessions` with `{"library_id":1}`. Save the returned session `id`.
4. `POST /query` with the session ID:

   ```json
   {
     "question": "What does the uploaded report say about retention?",
     "session_id": 1,
     "top_k": 3,
     "category": "general"
   }
   ```

The selected library and software policy documents are searched separately
using the same question embedding. `category` limits library documents only.
`top_k` is the maximum number of chunks **per corpus**, capped by
`MAX_TOP_K`, so both searches can contribute up to `2 * top_k` sources. Hits
below `MIN_SIMILARITY` are removed; remaining chunks are deduplicated and ranked
by similarity before generation.

The response includes `session_id`, `library_id`, the answer, and sources with
`source` set to `"upload"` or `"seed"`. The prompt labels uploaded documents and
software policies separately and requires answers grounded in the excerpts.

Membership is selected from SQL at query time. Moving or removing documents
therefore changes the next query's scope without re-embedding their content.

## API reference

| Method | Path | Body / purpose |
| --- | --- | --- |
| POST | `/libraries` | `{"name":"Research"}`; create a library |
| GET | `/libraries` | List libraries; `limit` and `offset` pagination |
| GET | `/libraries/{id}` | Library metadata |
| PATCH | `/libraries/{id}` | `{"name":"New name"}` |
| DELETE | `/libraries/{id}` | Preserve documents and sessions; clear library links |
| GET | `/libraries/{id}/documents` | List library documents; `limit`, `offset`, optional `category` |
| POST | `/libraries/{id}/documents` | `{"document_ids":[1,2]}`; assign or move documents |
| DELETE | `/libraries/{id}/documents` | `{"document_ids":[1,2]}`; remove documents from this library |
| DELETE | `/libraries/{id}/documents/{doc_id}` | Remove one document from this library |
| POST | `/sessions` | `{"library_id":1}`; create a session |
| GET | `/sessions` | List sessions; `limit` and `offset` pagination |
| GET | `/sessions/{id}` | Session and current library link |
| PATCH | `/sessions/{id}` | `{"library_id":2}`; choose another library |
| DELETE | `/sessions/{id}` | Delete the session, preserving its library and documents |
| POST | `/query` | `question`, optional `session_id`, `top_k`, `category` |
| POST | `/documents/upload` | Multipart `files`, optional `category`, optional `library_id` |
| GET | `/documents` | Optional `library_id` **or** `uncategorized=true`, category and pagination |

Library names are trimmed, nonempty, and at most 255 characters. Membership
requests require 1–1000 distinct positive document IDs and validate the entire
batch before changing any memberships. Assigning a document moves it from its
previous library. Removing a document from a library it does not belong to
returns 404. Duplicate uploads return the existing document and preserve its
current membership; use the membership endpoint to move it.

For backward compatibility, `/query` without `session_id` searches uncategorized
documents plus software policies. A session whose library was deleted searches
only software policies until `PATCH /sessions/{id}` selects an existing library.
An unknown session returns 404. A session stores the selected library; query
history is not persisted by these endpoints.

## Database upgrade and validation

Application startup creates `libraries` and `sessions` and adds the nullable,
indexed `documents.library_id` foreign key to an existing database. Both library
foreign keys use `ON DELETE SET NULL`. The additive upgrade runs inside a
transaction; a PostgreSQL advisory lock serializes concurrent app startup.
SQLite connections also enable foreign key enforcement. Startup can be run
again without changing existing document IDs, content, or categories.

Tests use SQLite and real Chroma collections with deterministic embeddings;
they require no model download, LLM call, or Neon connection. From the repository
root:

```bash
.venv/bin/python -m pytest src/policy_copilot_rag_service/tests src/policy_copilot_rag_service/rag/tests src/policy_copilot_rag_service/api/db/tests -q
```

The vector index remains process-local, as in the existing service. Startup
rebuilds it from SQL; each deployed worker indexes its own uploads.
