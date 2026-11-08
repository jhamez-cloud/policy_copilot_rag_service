# Workspace Data Isolation and Retrieval Security Policy

> **Document type:** Security policy  
> **Product:** [PRODUCT_NAME]  
> **Document ID:** 04_AI_AND_RAG-DATA_ISOLATION_AND_SECURITY  
> **Version:** 1.0  
> **Effective date:** [PUBLICATION_DATE]  
> **Last reviewed:** 8 November 2026  
> **Status:** Draft — requires review and completion before publication

---

## 1. Purpose

This policy describes the intended protection of user and workspace boundaries in the RAG system. It must be checked against the actual implementation before publication.

## 2. Access boundaries

A user should only be able to access documents, extracted text, embeddings, conversations and answers belonging to that user's account or an authorised workspace. Workspace membership and roles must be checked on every relevant API operation.

## 3. Retrieval controls

The RAG service should receive a verified user or workspace scope from the trusted application API. It must not trust a client-supplied tenant identifier without server-side authorisation. Retrieval queries must apply access filters before returning candidate passages.

## 4. Storage and index boundaries

The implementation should prevent cross-tenant access in:
- Original file storage.
- Extracted text and chunk storage.
- Vector indexes and metadata filters.
- Conversation and answer stores.
- Caches, temporary files and background jobs.
- Logs, exports and administrative tools.

Physical separation or logically enforced tenant identifiers may be used, depending on risk and architecture. The operator must document which model is implemented.

## 5. Administrative access

Staff and service accounts should receive least-privilege access, with access logging and periodic review. Support access to customer content should be limited to authorised purposes and controlled procedures.

## 6. Testing

The operator should conduct authorisation tests, cross-tenant retrieval tests, IDOR tests, cache isolation tests and access-control regression tests before release and after material changes.

## 7. Disclosure accuracy

Do not claim that data is encrypted, isolated, inaccessible to staff or never shared with providers unless those statements are verified against the deployed system and provider contracts.

---

## Document control

This document forms part of the [PRODUCT_NAME] policy library. The published version, effective date and current contact details displayed on the official website or application take precedence over any locally cached copy.

**Policy owner:** [LEGAL_ENTITY_OR_OPERATOR]  
**Policy contact:** [PRIVACY_OR_LEGAL_CONTACT_EMAIL]  
**Official website:** [PRODUCT_WEBSITE_URL]
