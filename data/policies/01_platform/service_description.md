# Service Description

> **Document type:** Service description  
> **Product:** [PRODUCT_NAME]  
> **Document ID:** 01_PLATFORM-SERVICE_DESCRIPTION  
> **Version:** 1.0  
> **Effective date:** [PUBLICATION_DATE]  
> **Last reviewed:** 8 November 2026  
> **Status:** Draft — requires review and completion before publication

---

## 1. Core workflow

The service generally follows this workflow:

1. **Upload:** An authenticated user selects a supported document.
2. **Validation:** The platform checks the file against configured type, size, security and processing restrictions.
3. **Extraction:** Text and, where supported, document structure are extracted.
4. **Preparation:** Extracted content may be cleaned, divided into passages or chunks, and associated with source metadata.
5. **Embedding and indexing:** Text segments may be converted into numerical representations and stored in a search index or vector database.
6. **Question:** The user submits a natural-language query.
7. **Retrieval:** The RAG service searches the user's authorised document collection for relevant passages.
8. **Generation:** An AI model receives the question and retrieved context and generates a response.
9. **Presentation:** The application returns the answer and, where implemented, source references or citations.

The exact technical implementation may evolve. The operator must update this description if the production workflow materially changes.

## 2. Service components

The product may contain:
- A frontend application.
- An application API responsible for authentication, user sessions and client-facing operations.
- A separate RAG service responsible for ingestion, indexing, retrieval and answer generation.
- File or object storage.
- A metadata database and search/vector index.
- Third-party embedding, reranking or generative AI providers.

The actual providers and processing locations must be disclosed in the privacy notice or an appropriate subprocessor list.

## 3. User responsibility

Users choose the files and questions. Users must ensure that they have the legal right to upload each file and that their use of the service complies with applicable law and the policies in this library.

## 4. No guaranteed result

The platform does not guarantee that every uploaded file will be processed successfully or that every question will produce a relevant answer. A response may be unavailable if there is no relevant evidence, the document is unreadable, a provider is unavailable or a usage limit is reached.

## 5. Features not promised

A feature is not included merely because it appears in a roadmap, prototype, marketing discussion or development environment. Only features expressly made available in the current product documentation or interface are part of the current service.

---

## Document control

This document forms part of the [PRODUCT_NAME] policy library. The published version, effective date and current contact details displayed on the official website or application take precedence over any locally cached copy.

**Policy owner:** [LEGAL_ENTITY_OR_OPERATOR]  
**Policy contact:** [PRIVACY_OR_LEGAL_CONTACT_EMAIL]  
**Official website:** [PRODUCT_WEBSITE_URL]
