# Legal details still owed by the platform owner

The Terms, Privacy, Cookie, Data Protection, Copyright and Contact pages are **drafts**. Nothing in them is invented: any detail not supplied below renders on the page as a highlighted `[TO BE PROVIDED: …]` placeholder, so an unfinished draft cannot be mistaken for real company details.

Set each value as a `NEXT_PUBLIC_LEGAL_*` variable (see `frontend/.env.local.example`; for container builds, pass them as build args, because the site bakes them in at build time). Leave a variable blank until you have the real answer.

| Environment variable | What is needed |
|---|---|
| `NEXT_PUBLIC_LEGAL_ENTITY_NAME` | Registered legal entity name |
| `NEXT_PUBLIC_LEGAL_ADDRESS` | Registered business address |
| `NEXT_PUBLIC_LEGAL_CONTACT_EMAIL` | Official contact email |
| `NEXT_PUBLIC_LEGAL_CONTACT_PHONE` | Official contact phone number |
| `NEXT_PUBLIC_LEGAL_DPO_CONTACT` | Data protection contact / officer, if applicable |
| `NEXT_PUBLIC_LEGAL_JURISDICTIONS` | Jurisdictions the service is offered in |
| `NEXT_PUBLIC_LEGAL_GOVERNING_LAW` | Governing law |
| `NEXT_PUBLIC_LEGAL_DISPUTE_RESOLUTION` | Dispute-resolution process |
| `NEXT_PUBLIC_LEGAL_REFUND_POLICY` | Refund policy for viewing bundles and fees |
| `NEXT_PUBLIC_LEGAL_HOSTING_PROVIDER` | Hosting provider |
| `NEXT_PUBLIC_LEGAL_DATA_LOCATION` | Where personal data is stored and any transfers outside Kenya |
| `NEXT_PUBLIC_LEGAL_RETENTION_ACCOUNT` | Retention period for account and profile data |
| `NEXT_PUBLIC_LEGAL_RETENTION_VIEWINGS` | Retention period for viewing requests and outcomes |
| `NEXT_PUBLIC_LEGAL_RETENTION_PAYMENTS` | Retention period for payment and fee records |
| `NEXT_PUBLIC_LEGAL_RETENTION_AUDIT` | Retention period for audit logs |
| `NEXT_PUBLIC_LEGAL_RETENTION_REPORTS` | Retention period for reports and disputes |
| `NEXT_PUBLIC_LEGAL_RETENTION_OTP` | Retention period for expired verification codes |
| `NEXT_PUBLIC_LEGAL_LAST_UPDATED` | Date these terms were last updated |

## Before publishing

1. Have a qualified lawyer or privacy professional review all six pages. The in-page draft banner says they have not been reviewed.
2. Fill in every variable above.
3. Set `NEXT_PUBLIC_LEGAL_STATUS=published` to remove the draft banner.
4. If the Terms or Privacy Policy change in a way users should re-accept, bump the version. `NEXT_PUBLIC_LEGAL_VERSION` (frontend) and `LEGAL_POLICY_VERSION` (backend) must match; it is stored with every consent record.
5. The account-deletion response is separate from the legal pages: `_deletion_context` in `backend/apps/accounts/views.py` hard-codes the sentence "The specific retention periods are set by the platform owner and are not yet published here." It does **not** read the values above, so update that sentence by hand once you have published retention periods.
