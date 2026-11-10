# Local frontend integration

The separate `insta-grad-frontend` Next.js project consumes the Policy Copilot API through its server-side `/api/policy/...` proxy. No monorepo or shared build is used. The frontend's `docs/API_INTEGRATION.md` records every endpoint's parameters, DTOs, feature mapping, RAG flow and verification.

Backend settings load `.env` from the backend repository root regardless of the process working directory. Keep existing database and Gemini provider credentials. Set `ADMIN_API_KEY` and match it with frontend server-only `POLICY_ADMIN_API_KEY`; never expose this key in a `NEXT_PUBLIC_` setting. Local frontend origins are `http://localhost:3000` and `http://127.0.0.1:3000` in `CORS_ALLOWED_ORIGINS`. Database/provider URLs remain their existing service configuration.

Run the backend independently from its repository root:

```bash
uv run uvicorn policy_copilot_rag_service.api.main:app --host 127.0.0.1 --port 8000
```

Start the frontend independently with `npm run dev` or `npm run build` followed by `npm start`. Its `.env.local` uses `POLICY_API_URL`, `POLICY_ADMIN_API_KEY`, `POLICY_ALLOWED_ORIGINS`, `POLICY_API_TIMEOUT_MS` and local `NEXT_PUBLIC_APP_URL`.

In this workspace the fresh backend runs on port 8001 because the pre-existing 8000 process was unresponsive. Frontend `.env.local` targets `http://127.0.0.1:8001`; example configurations retain port 8000.

The frontend uses real UTF-8 text/Markdown uploads, paginated library/document records, explicit persistent sessions, complete JSON answers and actual source documents. Category filters restrict uploads; software policies remain a separately searched shared corpus. Conversation transcripts stay only in the browser because the API has no messages/history endpoint. Each question is answered independently. Document membership removal and library deletion retain documents; permanent document deletion removes DB content and vector chunks.

Verification: the existing 47 backend tests pass, covering migrations, ingestion, membership transactions, sessions and scoped dual-corpus RAG retrieval. The frontend passed TypeScript, ESLint and a production build. Integration exercised all API operations through the proxy and received a live Gemini answer citing a temporary uploaded source. Test records were removed afterward.
