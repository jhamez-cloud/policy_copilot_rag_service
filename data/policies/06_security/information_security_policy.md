# Information Security Policy

> **Document type:** Security policy  
> **Product:** [PRODUCT_NAME]  
> **Document ID:** 06_SECURITY-INFORMATION_SECURITY_POLICY  
> **Version:** 1.0  
> **Effective date:** [PUBLICATION_DATE]  
> **Last reviewed:** 8 November 2026  
> **Status:** Draft — requires review and completion before publication

---

## 1. Objective

The operator aims to protect the confidentiality, integrity and availability of platform information through risk-appropriate technical and organisational controls.

## 2. Security governance

Security responsibilities are assigned to [SECURITY_OWNER_OR_TEAM]. Security risks, access permissions, dependencies and incidents should be reviewed periodically and after material architecture changes.

## 3. Technical controls

The operator should implement controls appropriate to the service, which may include:
- Encryption in transit and at rest where supported.
- Strong authentication and access control.
- Least-privilege permissions for staff and services.
- Secure secret storage and rotation.
- Input validation and file-type verification.
- Malware scanning where appropriate.
- Network and service isolation.
- Dependency and vulnerability management.
- Security logging and monitoring.
- Backups and recovery testing.
- Secure development and code review.
- Environment separation for development, staging and production.

Only controls actually implemented should be represented to users as existing safeguards.

## 4. RAG-specific security

The operator should protect original files, extracted text, chunks, embeddings, vector indexes, prompts, generated answers and temporary processing artifacts. Access checks must be enforced before retrieval and when displaying results.

## 5. Personnel and suppliers

Personnel with access to production systems should be authorised, trained and subject to confidentiality obligations. Third-party providers should be assessed based on the sensitivity of data and service risk.

## 6. Vulnerability reporting

Security concerns should be reported to [SECURITY_EMAIL]. Do not attempt unauthorised testing or access. The operator should publish a vulnerability disclosure process if it invites external security reports.

## 7. Limitations

No technical or organisational measure can guarantee absolute security. The operator will assess and improve controls as risks and technology evolve.

---

## Document control

This document forms part of the [PRODUCT_NAME] policy library. The published version, effective date and current contact details displayed on the official website or application take precedence over any locally cached copy.

**Policy owner:** [LEGAL_ENTITY_OR_OPERATOR]  
**Policy contact:** [PRIVACY_OR_LEGAL_CONTACT_EMAIL]  
**Official website:** [PRODUCT_WEBSITE_URL]
