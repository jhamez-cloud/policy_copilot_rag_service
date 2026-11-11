# Local frontend integration

The separate `insta-grad-frontend` Next.js project consumes the Policy Copilot API through its server-side `/api/policy/...` proxy. No monorepo or shared build is used. The frontend's `docs/API_INTEGRATION.md` records every endpoint's parameters, DTOs, feature mapping, RAG flow and verification.

Backend settings load `.env` from the backend repository root regardless of the process working directory. Keep existing database and Gemini provider credentials. Set `ADMIN_API_KEY` and match it with frontend server-only `POLICY_ADMIN_API_KEY`; never expose this key in a `NEXT_PUBLIC_` setting. Local frontend origins are `http://localhost:3000` and `http://127.0.0.1:3000` in `CORS_ALLOWED_ORIGINS`. Database/provider URLs remain their existing service configuration.

Run the backend independently from its repository root:

```bash
uv run uvicorn policy_copilot_rag_service.api.main:app --host 127.0.0.1 --port 8000
```

Start the frontend independently with `npm run dev` or `npm run build` followed by `npm start`. Its `.env.local` uses `POLICY_API_URL`, `POLICY_ADMIN_API_KEY`, `POLICY_ALLOWED_ORIGINS`, `POLICY_API_TIMEOUT_MS` and local `NEXT_PUBLIC_APP_URL`.

Gemini requests use `LLM_TIMEOUT_SECONDS` (default 60 seconds), passed to the SDK in milliseconds, with one attempt and no automatic retries. Keep this timeout below the frontend's `POLICY_API_TIMEOUT_MS` (default 90000), allowing time for retrieval and database access. Restart the backend after changing environment settings. Provider timeouts return 504 with an LLM-specific message; quota, configuration, empty-answer and other provider failures return 503 with a safe explanation. Backend logs include the model and elapsed generation time to distinguish provider failures from the proxy's own timeout.

In this workspace the backend runs on port 8000 and frontend `.env.local` targets `http://127.0.0.1:8000`. A previously stalled backend was restarted after adding the Gemini request timeout.

The frontend uses real UTF-8 text/Markdown uploads, paginated library/document records, explicit persistent sessions, complete JSON answers and actual source documents. Category filters restrict uploads; software policies remain a separately searched shared corpus. Conversation transcripts stay only in the browser because the API has no messages/history endpoint. Each question is answered independently. Document membership removal and library deletion retain documents; permanent document deletion removes DB content and vector chunks.

The backend now creates one built-in **Software policy** library during database initialization and assigns every seeded document to it, including existing policies and later seed files. This also runs when directory seeding is disabled or unavailable. `LibraryOut.is_system` identifies the read-only library independently of its name. Clients must disable rename, deletion, uploads and membership edits for it, and protect `source="seed"` documents in global management screens. The backend returns 403 for those operations, including moves into user libraries and global policy-document deletion. Sessions can select the built-in library normally; policies continue to contribute to queries from other libraries.

System library validation: all 75 offline backend tests pass, including additive legacy-library migration, preexisting seed backfill, content-based promotion, later seed files, missing directories, seed-disabled application startup, concurrent singleton creation, immutable API writes, atomic mixed moves and preserved custom-library/session behavior. These tests use SQLite and deterministic embeddings without contacting Neon or an LLM.

Verification: all 62 backend tests pass, covering migrations, ingestion, membership transactions, sessions, scoped dual-corpus RAG retrieval, SDK timeout units, single-attempt provider failures and API error responses. A live query for session 12 returned a provider timeout in approximately 59 seconds; health checks stayed responsive. Gemini returned `504 DEADLINE_EXCEEDED` even for a minimal generation request. Earlier frontend integration passed TypeScript, ESLint and a production build and exercised the API through the proxy; that earlier live Gemini check returned an answer citing a temporary uploaded source, and test records were removed afterward.
