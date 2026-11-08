# Retrieval-Augmented Generation (RAG) Service Policy

> **Document type:** AI service policy  
> **Product:** [PRODUCT_NAME]  
> **Document ID:** 04_AI_AND_RAG-RAG_SERVICE_POLICY  
> **Version:** 1.0  
> **Effective date:** [PUBLICATION_DATE]  
> **Last reviewed:** 8 November 2026  
> **Status:** Draft — requires review and completion before publication

---

## 1. What RAG means

Retrieval-Augmented Generation combines information retrieval with generative AI. The platform searches a user's indexed documents for passages relevant to a question and provides selected passages to an AI model as context for generating an answer.

RAG does not inherently alter a model's learned parameters. The product must not describe ordinary document indexing as fine-tuning.

## 2. Ingestion and indexing

A supported upload may be validated, scanned, parsed, text-extracted, normalised, divided into chunks, embedded and indexed. A file may fail if it is corrupt, encrypted, unsupported, too large, image-only where OCR is unavailable, password-protected or otherwise not processable.

## 3. Retrieval

Retrieval quality may depend on document quality, language, formatting, chunking, metadata, query wording, embedding model, search algorithm, reranking and configured retrieval limits. The service may not retrieve every relevant passage.

## 4. Answer generation

The model receives the question and retrieved context and generates a response. If the retrieved evidence is insufficient, the assistant should communicate uncertainty or state that the indexed documents do not contain enough information.

## 5. Source evidence

Where citations or source references are available, they should identify the document and relevant location. A citation is a navigation aid, not a guarantee that the answer is correct. Users should open and verify the original passage.

## 6. User collection boundaries

The service must retrieve only from documents the requesting user or workspace is authorised to access. The implementation should enforce tenant isolation at authentication, API, retrieval, storage and index layers.

## 7. Document changes

If a document is replaced or deleted, the corresponding derived content and index entries should be updated or removed according to the Retention Policy. Until processing completes, an index may temporarily reflect an earlier version; the interface should communicate processing status.

## 8. Provider and model changes

The operator may change embedding models, retrieval algorithms, vector databases or generative models. Such changes may affect answer style, speed and retrieval quality. Material data-processing changes will be reflected in the relevant privacy disclosures.

## 9. No source document requirement

The assistant does not independently request or select a user's private documents. Users are responsible for providing the documents they want included in their knowledge collection. The service may explain that an answer cannot be found if no relevant source is available.

---

## Document control

This document forms part of the [PRODUCT_NAME] policy library. The published version, effective date and current contact details displayed on the official website or application take precedence over any locally cached copy.

**Policy owner:** [LEGAL_ENTITY_OR_OPERATOR]  
**Policy contact:** [PRIVACY_OR_LEGAL_CONTACT_EMAIL]  
**Official website:** [PRODUCT_WEBSITE_URL]
