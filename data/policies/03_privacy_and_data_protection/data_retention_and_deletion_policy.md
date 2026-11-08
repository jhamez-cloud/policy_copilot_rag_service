# Data Retention and Deletion Policy

> **Document type:** Privacy policy  
> **Product:** [PRODUCT_NAME]  
> **Document ID:** 03_PRIVACY_AND_DATA_PROTECTION-DATA_RETENTION_AND_DELETION_POLICY  
> **Version:** 1.0  
> **Effective date:** [PUBLICATION_DATE]  
> **Last reviewed:** 8 November 2026  
> **Status:** Draft — requires review and completion before publication

---

## 1. Principle

The operator retains personal data and user content only for as long as reasonably necessary for the purpose for which it was collected, subject to legal, security, accounting and dispute-preservation requirements.

## 2. Data lifecycle

The system may create several representations of an upload:
1. Original file in object storage.
2. Extracted text or OCR output.
3. Normalised text and document metadata.
4. Chunks or passages.
5. Embeddings and vector-index entries.
6. Temporary processing files and job records.
7. Query, answer, citation and diagnostic logs.
8. Backups and disaster-recovery copies.

Deleting an original file does not necessarily delete all derived copies unless the deletion workflow explicitly covers them. The operator must implement and verify deletion propagation across each relevant store.

## 3. Retention schedule — complete before launch

| Data category | Purpose | Retention period |
|---|---|---|
| Account profile | Account operation | [PERIOD / ACCOUNT LIFETIME] |
| Original uploaded files | User document service | [PERIOD / UNTIL USER DELETES] |
| Extracted text and chunks | Retrieval | [PERIOD / UNTIL USER DELETES] |
| Embeddings and index entries | Semantic search | [PERIOD / UNTIL USER DELETES] |
| Conversations and answers | User history and service | [PERIOD] |
| Security logs | Security and abuse prevention | [PERIOD] |
| Billing records | Accounting and legal duties | [PERIOD REQUIRED BY LAW] |
| Backups | Recovery | [BACKUP CYCLE AND EXPIRY] |
| Support records | Issue resolution | [PERIOD] |

Do not publish this table until every period has been confirmed with engineering, finance and legal reviewers.

## 4. User deletion

Users may request deletion through [ACCOUNT SETTINGS / DELETION REQUEST URL / EMAIL]. The operator will verify the request, explain any applicable exceptions and process it within the legally required period.

The deletion process should cover originals, extracted text, chunks, embeddings, vector indexes, cached copies, conversation records and provider-held copies where the operator has the ability and legal obligation to request deletion.

## 5. Backups

Deleted data may remain in encrypted or access-restricted backups until the normal backup rotation expires. The expected maximum backup expiry is [PERIOD]. Data restored from backup must be subject to deletion requests and retention controls again.

## 6. Legal holds and exceptions

The operator may retain limited information where required by law, necessary to establish or defend legal claims, or needed to investigate security incidents. Retained data must be restricted to the relevant purpose and deleted when the justification ends.

## 7. Completion and confirmation

The operator should provide a confirmation when a deletion request is completed, while explaining any data that must remain and the reason for retaining it.

---

## Document control

This document forms part of the [PRODUCT_NAME] policy library. The published version, effective date and current contact details displayed on the official website or application take precedence over any locally cached copy.

**Policy owner:** [LEGAL_ENTITY_OR_OPERATOR]  
**Policy contact:** [PRIVACY_OR_LEGAL_CONTACT_EMAIL]  
**Official website:** [PRODUCT_WEBSITE_URL]
