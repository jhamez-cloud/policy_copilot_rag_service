# Document Upload and File Requirements Policy

> **Document type:** Upload policy  
> **Product:** [PRODUCT_NAME]  
> **Document ID:** 04_AI_AND_RAG-DOCUMENT_UPLOAD_POLICY  
> **Version:** 1.0  
> **Effective date:** [PUBLICATION_DATE]  
> **Last reviewed:** 8 November 2026  
> **Status:** Draft — requires review and completion before publication

---

## 1. User-controlled uploads

Users choose which documents to upload. The platform does not guarantee that a particular document is necessary or sufficient to answer a question. Users are responsible for ensuring that they have authority to upload and process each file.

## 2. Supported format

The currently supported upload format is **Markdown (`.md`)**.

If additional formats are enabled in production, list them here only after testing:
- [ADDITIONAL_FORMAT_AND_VERSION]
- [ADDITIONAL_FORMAT_AND_VERSION]

Files should use UTF-8 text where possible. Unsupported, encrypted, password-protected, malformed or unreadable files may be rejected.

## 3. File-size and quantity limits

The current production limits are:
- Maximum file size: [MAX_FILE_SIZE]
- Maximum files per account or workspace: [MAX_FILE_COUNT]
- Maximum total storage: [MAX_TOTAL_STORAGE]
- Maximum content length or processing limit: [MAX_CONTENT_LIMIT]
- Rate or processing limits: [RATE_LIMITS]

These values must match server-side enforcement, not merely frontend validation. If limits vary by plan, publish a plan-specific table or link to a live limits page.

## 4. Upload validation

The service may validate extension, MIME type, file signature, size, encoding and content. The service may reject a file that fails validation or presents a security or processing risk.

## 5. Content responsibility

Users must not upload content that:
- They do not own or have permission to use.
- Contains personal data they are not authorised to process.
- Breaches confidentiality or contractual restrictions.
- Violates copyright or other intellectual property rights.
- Is unlawful or prohibited by the Acceptable Use Policy.

## 6. Document quality

For best results, use clear headings, descriptive section titles, meaningful filenames and text-based Markdown. Avoid scanned images of text unless image/OCR processing is expressly supported. Large documents may be divided into smaller, logically organised files.

## 7. Processing status and failure

The application should show whether a file is queued, processing, indexed, failed or deleted. A successful upload does not necessarily mean that indexing has completed. Users should not assume a document is searchable until the interface confirms successful processing.

## 8. File security and retention

Uploaded files and derived content are handled according to the Privacy Policy, Information Security Policy and Data Retention and Deletion Policy. The operator must document actual scanning, storage, encryption, backup and deletion controls.

## 9. Changes to limits

Supported formats, file-size limits, quotas and processing limits may change as infrastructure, provider terms, security requirements and service plans evolve. Material changes will be communicated through [NOTICE_CHANNEL] where appropriate.

---

## Document control

This document forms part of the [PRODUCT_NAME] policy library. The published version, effective date and current contact details displayed on the official website or application take precedence over any locally cached copy.

**Policy owner:** [LEGAL_ENTITY_OR_OPERATOR]  
**Policy contact:** [PRIVACY_OR_LEGAL_CONTACT_EMAIL]  
**Official website:** [PRODUCT_WEBSITE_URL]
