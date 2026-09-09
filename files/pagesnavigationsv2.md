Exactly. This is the missing **implementation contract**.

For AINCURU × TAXLA, every interactive page should be specified in this exact chain:

```text
PAGE
 ↓
ROUTE
 ↓
BUTTON / ACTION
 ↓
FRONTEND FUNCTION
 ↓
HTTP API
 ↓
BACKEND SERVICE
 ↓
DATABASE CHANGE
 ↓
STATE TRANSITION
 ↓
EVENT
 ↓
BACKGROUND JOB
 ↓
RESULT
 ↓
UI UPDATE
 ↓
NEXT AVAILABLE ACTION
```

Your current project does **not** yet have this level of end-to-end wiring. For example, the existing frontend has buttons with no handlers, mock pages, and only a handful of API functions; the backend currently exposes only a small set of application/document/NIC/automation/OTP routes.  

Below is the **updated page-by-page implementation contract** I would use.

---

# AINCURU × TAXLA

# COMPLETE PAGE → BUTTON → API → STATE → JOB → UI CONTRACT

## 1. Route architecture

```text
PUBLIC
├── /
├── /login
├── /forgot-password
└── /reset-password

APPLICATION
├── /dashboard
├── /work-queue
│
├── /applications
├── /applications/new
└── /applications/:applicationId
    ├── /overview
    ├── /documents
    ├── /data
    ├── /nic
    ├── /workflow
    ├── /automation
    ├── /approvals
    ├── /timeline
    └── /artifacts

CLIENTS
├── /clients
├── /clients/new
└── /clients/:clientId
    ├── /overview
    ├── /applications
    ├── /documents
    ├── /certificates
    └── /activity

PLATFORM
├── /documents
├── /automations
├── /workflows
├── /approvals
├── /notifications
├── /reports
├── /audit
└── /integrations

AI FACTORY
├── /ai
├── /ai/models
├── /ai/agents
├── /ai/prompts
├── /ai/runs
└── /ai/evaluations

ADMIN
├── /admin/users
├── /admin/roles
├── /admin/branches
├── /admin/settings
└── /admin/system

ERROR
├── /403
├── /404
└── /500
```

The current project only has a small subset of these routes; Automations, Workflows and AI dashboards are currently absent. 

---

# 2. GLOBAL NAVIGATION CONTRACT

Every authenticated page:

```text
Sidebar
Topbar
Breadcrumbs
Page title
Page actions
Main content
```

### Sidebar

```text
Dashboard
Work Queue
Applications
Clients
Documents
Automations
Workflows
AI Factory
Approvals
Integrations
Reports
Audit
Administration
```

### Global topbar

```text
Search
Notifications
Help
User menu
Logout
```

### Sidebar click

Example:

```text
Applications
 ↓
GET /applications
 ↓
/applications
```

No business side effect.

---

# 3. `/login`

## Page

```text
/login
```

## UI

```text
Email
Password

[ Sign In ]

Forgot password?
```

## Sign In

```text
UI
 ↓
login()
 ↓
POST /api/v1/auth/login
 ↓
AuthService
 ↓
validate credentials
 ↓
create access token
 ↓
create refresh session
 ↓
set secure refresh cookie
 ↓
return user/session
 ↓
frontend stores access token in memory
 ↓
GET /api/v1/auth/me
 ↓
navigate /dashboard
```

### State

```text
UNAUTHENTICATED
→ AUTHENTICATED
```

### Background job

None.

### UI next

```text
/dashboard
```

The current code has no real login page and instead auto-logs in using hardcoded credentials. 

---

# 4. Forgot password

## `/forgot-password`

### Submit

```text
POST /api/v1/auth/password/forgot
```

Backend:

```text
verify account
 ↓
create reset challenge
 ↓
send notification
```

Job:

```text
notification-worker
```

UI:

```text
Enter verification code
```

Then:

```text
/reset-password
```

---

# 5. `/dashboard`

## Initial load

```text
GET /api/v1/dashboard/summary
GET /api/v1/dashboard/pipeline
GET /api/v1/dashboard/attention
GET /api/v1/system/health
```

UI:

```text
Total
Processing
Review
OTP
Exceptions
Completed
```

---

## `+ New Application`

```text
click
 ↓
/applications/new
```

No backend call yet.

---

## KPI: OTP Required

```text
click
 ↓
/work-queue?state=OTP_REQUIRED
```

---

## KPI: Exceptions

```text
click
 ↓
/work-queue?state=EXCEPTION
```

---

## Recent application row

```text
click
 ↓
/applications/:id/overview
```

---

# 6. `/work-queue`

This is the operational inbox.

## Load

```text
GET /api/v1/work-queue
```

Filters:

```text
state
branch
assignee
workflow
priority
date
```

---

## Open

```text
click
 ↓
/applications/:id/overview
```

---

## Assign

```text
click
 ↓
assignment modal
```

Confirm:

```text
PATCH /api/v1/applications/:id/assignment
 ↓
ApplicationService
 ↓
DB assignment updated
 ↓
AUDIT_EVENT
 ↓
NOTIFICATION_EVENT
 ↓
notification-worker
```

UI:

```text
toast "Application assigned"
```

---

## Claim

```text
POST /api/v1/applications/:id/claim
```

State:

```text
UNASSIGNED
→ ASSIGNED
```

---

## Release

```text
POST /api/v1/applications/:id/release
```

State:

```text
ASSIGNED
→ UNASSIGNED
```

---

## Retry

```text
POST /api/v1/executions/:executionId/retry
```

State:

```text
FAILED
→ RETRY_QUEUED
```

Job:

```text
appropriate worker queue
```

---

# 7. `/applications`

## Load

```text
GET /api/v1/applications
```

Filters:

```text
search
status
workflow_type
branch
assignee
date
```

---

## New Application

```text
click
 ↓
/applications/new
```

The current button does nothing, so this is one of the first concrete navigation fixes. 

---

## Row click

```text
/applications/:id/overview
```

---

## Bulk select

Possible actions:

```text
Assign
Export
Archive
```

Bulk mutations should go through dedicated bulk APIs rather than firing hundreds of individual requests.

---

# 8. `/applications/new`

This is an **application creation wizard**.

## Step 1 — Workflow

```text
New Udyam Registration
Udyam Update
Udyam Cancellation
UAM Migration
Assisted Migration
Verify
Print Certificate
Forgot Number
```

This is where you separate the workflows instead of creating one monster form.

---

## Step 2 — Client

```text
Select existing client
OR
Create client
```

### Create client

```text
POST /api/v1/clients
```

Result:

```text
client_id
```

Continue:

```text
/applications/new?client=:id
```

---

## Step 3 — Application creation

```text
POST /api/v1/applications
```

Request:

```text
client_id
workflow_type
branch_id
```

Backend:

```text
ApplicationService.create()
 ↓
DB application
 ↓
Workflow instance
 ↓
AUDIT
 ↓
WORKFLOW_CREATED
```

State:

```text
DRAFT
```

Then navigate:

```text
/applications/:id/overview
```

---

# 9. `/applications/:id/overview`

This is the application's command center.

## Initial API calls

```text
GET /applications/:id
GET /applications/:id/summary
GET /applications/:id/actions
GET /applications/:id/permissions
GET /applications/:id/workflow
```

The final endpoint is especially important because the frontend should ask:

> What actions are currently legal?

rather than inventing buttons locally.

---

# 10. Action bar

Possible buttons:

```text
Upload Documents
Review Data
Review NIC
Start Automation
Resume
Retry
Enter OTP
Final Review
View Certificate
```

But **only state-valid and role-valid actions appear**.

The action availability should come from:

```text
current_state
+
user_permissions
+
workflow_definition
```

---

# 11. Overview → Upload Documents

```text
click
 ↓
/applications/:id/documents
```

---

# 12. Overview → Data

```text
click
 ↓
/applications/:id/data
```

---

# 13. Overview → NIC

```text
click
 ↓
/applications/:id/nic
```

---

# 14. Overview → Workflow

```text
click
 ↓
/applications/:id/workflow
```

---

# 15. Overview → Automation

```text
click
 ↓
/applications/:id/automation
```

---

# 16. Overview → Approvals

```text
click
 ↓
/applications/:id/approvals
```

---

# 17. `/applications/:id/documents`

## Load

```text
GET /api/v1/applications/:id/documents
```

---

## Upload Document

User selects:

```text
Document Type
File
```

Click:

```text
[Upload]
```

Flow:

```text
Browser
 ↓
POST /api/v1/applications/:id/documents
multipart/form-data
 ↓
DocumentService
 ↓
file validation
 ↓
hash
 ↓
store file
 ↓
create Document
 ↓
AUDIT
 ↓
DOCUMENT_UPLOADED
 ↓
queue OCR
```

State:

```text
DOCUMENT_PENDING
→ OCR_QUEUED
```

Job:

```text
ocr-worker
```

UI immediately:

```text
Uploaded
Processing OCR...
```

The current backend already has the document upload endpoint and 202 behavior, but the OCR worker still uses mocked OCR text.  

---

# 18. Document processing chain

```text
UPLOAD
 ↓
OCR JOB
 ↓
PaddleOCR
 ↓
OCR RESULT
 ↓
EXTRACTION JOB
 ↓
Ollama
 ↓
EXTRACTION RESULT
 ↓
VALIDATION JOB
 ↓
RESULT
```

Each step produces an event.

---

# 19. Document row

Example:

```text
PAN.pdf

Uploaded ✓
OCR ✓
Extraction ✓
Validation ⚠

[View]
[Reprocess]
```

---

# 20. View Document

```text
click
 ↓
/applications/:id/documents/:documentId
```

---

# 21. Reprocess Document

```text
POST /api/v1/documents/:documentId/reprocess
```

Backend:

```text
document status
→ REPROCESSING
```

Job:

```text
ocr-worker
```

UI:

```text
Processing...
```

---

# 22. Delete/replace document

Don't immediately hard-delete.

Use:

```text
POST /documents/:id/replace
```

or soft-delete.

Reason:

Auditability.

---

# 23. `/applications/:id/documents/:documentId`

Layout:

```text
LEFT
Document viewer

RIGHT
Extracted information
Validation
Confidence
Actions
```

This is one of the major pieces currently missing from the implementation. 

---

# 24. Document Viewer actions

```text
Zoom +
Zoom -
Rotate
Previous page
Next page
Download
Open fullscreen
```

These are frontend-only unless download access requires an API.

---

# 25. Extraction field

Example:

```text
PAN
ABCDE1234F
99%

Source:
PAN.pdf page 1

[Edit]
```

---

# 26. Edit extracted field

```text
PATCH /api/v1/extractions/:fieldId
```

Backend:

```text
validate
 ↓
persist correction
 ↓
audit
 ↓
mark downstream validation stale
```

UI:

```text
Human corrected
```

---

# 27. Data review

When all extracted data is ready:

```text
state:
EXTRACTED
```

Reviewer action:

```text
[Approve Data]
```

API:

```text
POST /api/v1/applications/:id/data/approve
```

Backend:

```text
validate all mandatory fields
 ↓
create review
 ↓
state:
EXTRACTED
→ VALIDATION
```

Then:

```text
queue validation job
```

---

# 28. Validation job

```text
VALIDATION
 ↓
ValidationService
 ↓
schema checks
 ↓
cross-field checks
 ↓
source consistency
 ↓
financial checks
 ↓
result
```

Possible outcomes:

```text
VALID
REVIEW_REQUIRED
EXCEPTION
```

This is important because the current validation engine reportedly jumps to NIC review without actually using the confidence branching documented by the project. 

---

# 29. Confidence logic

```text
HIGH
→ auto-verified

MEDIUM
→ review required

LOW
→ mandatory human review
```

These are currently documented project thresholds, not official Udyam rules. 

---

# 30. `/applications/:id/data`

Load:

```text
GET /api/v1/applications/:id/data
GET /api/v1/applications/:id/validation
```

Sections:

```text
Applicant
Entity
Ownership
Address
Units
Legacy
Bank
Business
Employment
Financial
Services
DIC
Declarations
Verification
```

---

# 31. Save field

```text
PATCH /api/v1/applications/:id/data
```

Backend:

```text
DataService
 ↓
schema validation
 ↓
business validation
 ↓
save
 ↓
audit
 ↓
possibly invalidate dependent calculations
```

---

# 32. Recalculate

For fields affecting financial classification:

```text
POST /api/v1/applications/:id/recalculate
```

Job may be synchronous if fast enough.

Output:

```text
investment
turnover
MSME category
```

---

# 33. `/applications/:id/nic`

Load:

```text
GET /api/v1/applications/:id/nic
```

---

# 34. Generate NIC suggestions

```text
[Generate Suggestions]
```

API:

```text
POST /api/v1/applications/:id/nic/suggest
```

Backend:

```text
NICService
 ↓
Tier A
 ↓
Tier B
 ↓
Tier C
 ↓
persist suggestions
```

Job:

```text
ai_queue
```

---

# 35. NIC result

```text
Top candidate
94%

Candidate 2
82%

Candidate 3
74%
```

Each has:

```text
code
description
score
rationale
```

---

# 36. NIC approve

```text
[Approve]
```

API:

```text
POST /api/v1/applications/:id/nic/approve
```

Backend:

```text
Reviewer permission
 ↓
persist approved NIC
 ↓
review record
 ↓
audit
 ↓
state:
NIC_REVIEW
→ READY_FOR_PORTAL
```

Your existing project already exposes `/nic/search` and `/nic/approve`, but role enforcement is currently incomplete.  

---

# 37. NIC override

```text
[Choose Different Code]
```

Search:

```text
POST /api/v1/nic/search
```

Then:

```text
select
 ↓
POST /nic/approve
```

Store:

```text
decision_type = HUMAN_OVERRIDE
```

---

# 38. `/applications/:id/workflow`

Load:

```text
GET /api/v1/applications/:id/workflow
GET /api/v1/applications/:id/workflow/events
```

UI:

```text
✓ INIT
✓ DOCUMENTS
✓ OCR
✓ EXTRACTION
✓ VALIDATION
✓ NIC
● PORTAL
○ OTP
○ REVIEW
○ COMPLETE
```

---

# 39. Workflow node click

```text
click NODE_OCR
 ↓
GET /api/v1/workflow-events/:id
```

Show:

```text
worker
start
end
duration
result
error
retry
```

---

# 40. `/applications/:id/automation`

Load:

```text
GET /api/v1/applications/:id/automation
GET /api/v1/applications/:id/portal-session
```

Show:

```text
Browser status
Portal stage
Current action
Screenshot
Logs
```

---

# 41. Start Automation

Button only when:

```text
READY_FOR_PORTAL
+
required fields valid
+
NIC approved
+
user has execute permission
```

Click:

```text
POST /api/v1/applications/:id/automation/start
```

Backend:

```text
validate state
 ↓
create PortalSession
 ↓
create WorkflowExecution
 ↓
state:
READY_FOR_PORTAL
→ PORTAL_RUNNING
 ↓
enqueue browser job
```

Job:

```text
browser_queue
```

The current backend has this endpoint, but the actual browser implementation is incomplete. 

---

# 42. Browser worker

```text
browser-worker
 ↓
BrowserManager
 ↓
Playwright
 ↓
Udyam Page Object
```

Each action:

```text
action started
 ↓
portal response
 ↓
action completed
```

---

# 43. Portal screenshot

After significant steps:

```text
screenshot
 ↓
artifact storage
 ↓
portal_session artifact
```

UI receives:

```text
EXECUTION_SCREENSHOT_READY
```

---

# 44. Human challenge

If portal requires:

```text
OTP
or
CAPTCHA/verification code
```

worker does:

```text
save checkpoint
 ↓
state = OTP_REQUIRED / HUMAN_CHALLENGE
 ↓
persist portal checkpoint
 ↓
release worker
```

UI:

```text
Human action required
```

---

# 45. `/applications/:id/otp`

Load:

```text
GET /api/v1/applications/:id/checkpoint
```

Show:

```text
OTP Required

[ _ _ _ _ _ _ ]

[ Verify ]
```

---

# 46. Verify OTP

```text
POST /api/v1/applications/:id/otp
```

Backend:

```text
authenticate user
 ↓
verify application state
 ↓
verify checkpoint
 ↓
validate OTP
 ↓
never log OTP
 ↓
persist verification event
 ↓
state:
OTP_REQUIRED
→ OTP_VERIFIED
 ↓
enqueue resume
```

Job:

```text
browser_queue
```

The current implementation already has an OTP endpoint and Redis publish mechanism, but the long-term design needs durable checkpoint handling rather than treating Redis alone as the state owner. 

---

# 47. OTP timeout

Project specification currently states:

```text
3 minutes
```

After expiry:

```text
OTP_REQUIRED
→ EXCEPTION
```

UI:

```text
OTP expired

[Resend OTP]
```

No OTP value is logged. 

---

# 48. Resume browser

```text
otp verified
 ↓
enqueue browser resume
 ↓
browser worker loads checkpoint
 ↓
continues from portal step
```

Do not restart from step 1 unnecessarily.

---

# 49. Portal validation error

Browser detects:

```text
portal validation error
```

Flow:

```text
capture screenshot
 ↓
capture visible error
 ↓
PortalSession error
 ↓
state = EXCEPTION
 ↓
notify operator
```

UI:

```text
Portal rejected the submitted field.

Reason:
...

[Resolve]
[Retry]
```

---

# 50. Browser timeout

```text
browser action
 ↓
timeout
 ↓
screenshot
 ↓
error artifact
 ↓
EXCEPTION
 ↓
notification
```

Your current documentation already calls for screenshot capture on DOM timeout. 

---

# 51. `/applications/:id/approvals`

Load:

```text
GET /api/v1/applications/:id/reviews
```

Show:

```text
Data Review
NIC Approval
Exception Review
Final Submission
```

---

# 52. Approve button

```text
POST /api/v1/applications/:id/reviews/:reviewId/approve
```

Backend:

```text
permission
 ↓
state validation
 ↓
approval
 ↓
audit
 ↓
trigger next workflow node
```

---

# 53. Reject button

```text
POST /api/v1/applications/:id/reviews/:reviewId/reject
```

Body:

```text
reason
```

Backend:

```text
review = REJECTED
 ↓
reason stored
 ↓
audit
 ↓
state = EXCEPTION or previous review state
```

Rejection reason should be mandatory; this matches the project rules. 

---

# 54. Final Review

UI displays:

```text
Application summary

Documents ✓
Data ✓
NIC ✓
Portal ✓
Declarations ✓

[Reject]
[Approve & Submit]
```

API:

```text
POST /api/v1/applications/:id/final-review/approve
```

Backend verifies:

```text
all required data
all required approvals
current state
user permission
```

Then:

```text
HUMAN_REVIEW
→ APPROVED
→ SUBMITTING
```

and queues final browser action.

---

# 55. Final OTP

If external portal requires a final OTP:

```text
SUBMITTING
→ FINAL_OTP_REQUIRED
```

UI:

```text
Final OTP required
```

Then:

```text
POST /applications/:id/otp
```

but with:

```text
checkpoint_id
purpose = FINAL_SUBMISSION
```

This is why the OTP model needs a **purpose** rather than treating every OTP as identical.

---

# 56. External submission

Browser:

```text
submit
 ↓
portal response
```

Success:

```text
SUBMITTING
→ SUBMITTED
```

Then:

```text
external processing
```

---

# 57. Certificate retrieval

Worker either receives certificate availability or uses the relevant retrieval step.

```text
certificate available
 ↓
download
 ↓
hash
 ↓
store artifact
 ↓
create Certificate record
 ↓
state:
CERTIFICATE_READY
```

Then:

```text
CERTIFICATE_READY
→ COMPLETED
```

---

# 58. Artifacts

## `/applications/:id/artifacts`

Load:

```text
GET /api/v1/applications/:id/artifacts
```

Types:

```text
source document
OCR output
screenshots
portal evidence
certificate
generated report
```

---

# 59. Certificate button

```text
[View]
```

→ certificate viewer

```text
[Download]
```

→ signed/authorized artifact download

```text
GET /api/v1/artifacts/:id/download
```

---

# 60. `/applications/:id/timeline`

Load:

```text
GET /api/v1/applications/:id/timeline
```

Timeline should be built from:

```text
workflow_events
audit_logs
reviews
execution events
```

not frontend-generated fake timestamps.

---

# 61. `/applications/:id/timeline` event click

```text
click
 ↓
event details drawer
```

Show:

```text
actor
event
timestamp
state before
state after
execution
source
```

---

# 62. `/clients`

Load:

```text
GET /api/v1/clients
```

Current `/clients` uses hardcoded data, so this needs to be replaced. 

---

# 63. Add Client

```text
click
 ↓
/clients/new
```

Submit:

```text
POST /api/v1/clients
 ↓
Client created
 ↓
audit
```

Then:

```text
/clients/:id/overview
```

---

# 64. `/clients/:id/overview`

Load:

```text
GET /clients/:id
GET /clients/:id/summary
```

Show:

```text
Contact
Business
Active registrations
Certificates
Recent activity
```

---

# 65. Client → Applications

```text
/clients/:id/applications
```

API:

```text
GET /api/v1/clients/:id/applications
```

Click application:

```text
/applications/:applicationId/overview
```

---

# 66. Client → Documents

```text
/clients/:id/documents
```

API:

```text
GET /api/v1/clients/:id/documents
```

---

# 67. Client → Certificates

```text
/clients/:id/certificates
```

API:

```text
GET /api/v1/clients/:id/certificates
```

---

# 68. `/documents`

Global document library.

```text
GET /api/v1/documents
```

Search:

```text
filename
client
application
document type
status
```

Click:

```text
→ application document viewer
```

---

# 69. `/automations`

Show automation catalog:

```text
Udyam New Registration
Udyam Update
Udyam Cancellation
Udyam Verify
Udyam Print Certificate
Udyam Forgot Number
UAM Migration
Assisted Migration
UAP
```

The current frontend doesn't have this route. 

---

# 70. Automation card

```text
[Run]
```

does not directly execute.

It should:

```text
Run
 ↓
create application/workflow
 ↓
/applications/:id
```

This prevents automation definitions from becoming detached from application records.

---

# 71. `/workflows`

Load:

```text
GET /api/v1/workflows
```

Show:

```text
Workflow
Version
Active
Executions
Success
Failures
```

---

# 72. Workflow detail

```text
/workflows/:workflowId
```

Show:

```text
nodes
transitions
checkpoints
retry policy
version
```

For V1, read-only visualization is enough.

Your own specification explicitly selected a hardcoded Python DAG for V1 rather than a configurable visual workflow editor. 

---

# 73. `/workflows/:id/executions`

```text
GET /api/v1/workflows/:id/executions
```

Click:

```text
/executions/:executionId
```

---

# 74. Execution detail

Show:

```text
Execution ID
Application
Workflow version
Start
End
Current node
Worker
Retries
Error
```

Actions:

```text
Retry
Cancel
Resume
```

only when legal.

---

# 75. `/ai`

AI Factory overview.

```text
GET /api/v1/ai/summary
```

Show:

```text
AI runs
Success
Failures
Latency
Token usage
Model usage
```

---

# 76. `/ai/agents`

```text
GET /api/v1/ai/agents
```

Agent cards:

```text
Entity Extraction
NIC Classification
Validation Assistant
Document Classification
```

---

# 77. Agent detail

```text
/ai/agents/:agentId
```

Show:

```text
Purpose
Input
Output
Model
Prompt version
Allowed tools
Runs
Evaluation
```

---

# 78. `/ai/prompts`

```text
GET /api/v1/ai/prompts
```

Actions:

```text
Create version
Compare
Evaluate
Archive
```

---

# 79. Prompt version

Creating a new version:

```text
POST /api/v1/ai/prompts/:id/versions
```

Never silently modify an existing production prompt.

---

# 80. `/ai/runs`

```text
GET /api/v1/ai/runs
```

Click:

```text
/ai/runs/:id
```

Show:

```text
agent
model
prompt version
latency
schema validation
result
failure
```

---

# 81. `/ai/evaluations`

Load:

```text
GET /api/v1/ai/evaluations
```

Run evaluation:

```text
POST /api/v1/ai/evaluations/run
```

Job:

```text
ai-evaluation-worker
```

Result:

```text
accuracy
parse rate
hallucination rate
latency
```

---

# 82. `/approvals`

This is the centralized human work center.

```text
GET /api/v1/approvals
```

Tabs:

```text
Data
NIC
Exceptions
Final
```

Click approval:

```text
→ application review page
```

---

# 83. `/notifications`

```text
GET /api/v1/notifications
```

Notification click:

```text
OTP required
→ /applications/:id/automation
```

or:

```text
Review required
→ /applications/:id/approvals
```

---

# 84. `/reports`

Current page uses hardcoded statistics, so it must be backed by real aggregation queries. 

APIs:

```text
GET /api/v1/reports/overview
GET /api/v1/reports/processing
GET /api/v1/reports/automation
GET /api/v1/reports/ai
GET /api/v1/reports/branches
```

---

# 85. Export

```text
[Export CSV]
```

→

```text
GET /api/v1/reports/export?...
```

Generate server-side.

Then:

```text
download file
```

The current Export CSV button has no implementation. 

---

# 86. `/audit`

```text
GET /api/v1/audit
```

Filters:

```text
actor
application
event
branch
date
```

---

# 87. Audit event detail

```text
GET /api/v1/audit/:eventId
```

Show:

```text
Actor
Action
Object
Before
After
Timestamp
Trace ID
```

Never show secrets or OTP values.

---

# 88. `/integrations`

```text
GET /api/v1/integrations
```

Cards:

```text
Udyam
Ollama
OCR
Storage
Notifications
```

---

# 89. Integration health

```text
GET /api/v1/integrations/:id/health
```

UI:

```text
Connected
Degraded
Unavailable
```

---

# 90. `/admin/users`

```text
GET /api/v1/admin/users
```

### Add User

```text
POST /api/v1/admin/users
```

Fields:

```text
name
email
role
branch
```

---

# 91. `/admin/branches`

```text
GET /api/v1/admin/branches
```

Add:

```text
POST /api/v1/admin/branches
```

Edit:

```text
PATCH /api/v1/admin/branches/:id
```

---

# 92. `/admin/roles`

Show:

```text
SUPER_ADMIN
BRANCH_ADMIN
OPERATOR
REVIEWER
```

Permission matrix:

```text
applications.read
applications.create
applications.edit
documents.write
nic.approve
automation.execute
final_review.approve
admin.users
admin.branches
```

---

# 93. `/admin/settings`

Settings should be real, not placeholder tabs.

Current settings contains unfinished panels and a non-functional Save button. 

Sections:

```text
General
AI
Automation
Storage
Notifications
Security
```

Save:

```text
PATCH /api/v1/admin/settings
```

---

# 94. WebSocket / realtime contract

Don't let every component open its own socket.

Use:

```text
GET /api/v1/events/stream
```

or authenticated WebSocket:

```text
/ws
```

Subscribe to:

```text
application:{id}
```

Events:

```text
APPLICATION_UPDATED
DOCUMENT_UPDATED
OCR_COMPLETED
EXTRACTION_COMPLETED
VALIDATION_COMPLETED
NIC_UPDATED
EXECUTION_UPDATED
CHECKPOINT_CREATED
NOTIFICATION_CREATED
```

Frontend reacts to the event by invalidating the appropriate TanStack Query.

The current implementation instead refetches broadly on every WebSocket message, which the audit identifies as a weakness. 

---

# 95. API architecture

The existing backend currently has only:

```text
/auth
/applications
/documents
/workflow
/ws
```

with endpoints such as applications CRUD, document upload, NIC search/approval, automation start and OTP. 

The finished platform needs the API surface to grow into:

```text
/api/v1
│
├── auth
├── me
├── dashboard
├── work-queue
│
├── users
├── branches
├── roles
│
├── clients
├── applications
│
├── documents
├── extractions
├── validation
├── nic
│
├── workflows
├── executions
├── checkpoints
├── approvals
│
├── automation
├── portal-sessions
├── artifacts
│
├── ai
├── integrations
├── notifications
├── reports
└── audit
```

---

# 96. The critical state/event/job table

This is the piece you specifically asked for.

| User action          | API                                | State change           | Event                   | Background job    | UI next               |
| -------------------- | ---------------------------------- | ---------------------- | ----------------------- | ----------------- | --------------------- |
| Create application   | `POST /applications`               | `DRAFT`                | `APPLICATION_CREATED`   | none              | Application workspace |
| Upload document      | `POST /applications/:id/documents` | `DOCUMENTS_PROCESSING` | `DOCUMENT_UPLOADED`     | OCR               | Processing indicator  |
| OCR completes        | internal                           | `OCR_COMPLETED`        | `OCR_COMPLETED`         | extraction        | Extraction progress   |
| Extraction completes | internal                           | `EXTRACTED`            | `EXTRACTION_COMPLETED`  | validation        | Data review           |
| Approve data         | `POST .../data/approve`            | `VALIDATION`           | `DATA_REVIEW_APPROVED`  | validation        | Validation screen     |
| Validation passes    | internal                           | `NIC_REVIEW`           | `VALIDATION_COMPLETED`  | NIC               | NIC review            |
| Generate NIC         | `POST .../nic/suggest`             | `NIC_REVIEW`           | `NIC_SUGGESTED`         | AI/NIC            | Suggestions           |
| Approve NIC          | `POST .../nic/approve`             | `READY_FOR_PORTAL`     | `NIC_REVIEW_APPROVED`   | none              | Start automation      |
| Start automation     | `POST .../automation/start`        | `PORTAL_RUNNING`       | `PORTAL_STARTED`        | browser           | Automation screen     |
| OTP required         | internal                           | `OTP_REQUIRED`         | `OTP_REQUIRED`          | worker released   | OTP UI                |
| Submit OTP           | `POST .../otp`                     | `OTP_VERIFIED`         | `OTP_SUBMITTED`         | browser resume    | Automation continues  |
| Final approval       | `POST .../final-review/approve`    | `SUBMITTING`           | `FINAL_APPROVED`        | browser           | Submission screen     |
| Portal submitted     | internal                           | `SUBMITTED`            | `SUBMISSION_COMPLETED`  | retrieval/process | Processing            |
| Certificate ready    | internal                           | `CERTIFICATE_READY`    | `CERTIFICATE_READY`     | artifact handling | Certificate           |
| Complete             | internal                           | `COMPLETED`            | `APPLICATION_COMPLETED` | notification      | Completed state       |

The state sequence aligns with the project's existing documented state machine: `NEW → DOCUMENTS_UPLOADED → PROCESSING → EXTRACTED → VALIDATION → NIC_REVIEW → READY_FOR_PORTAL → PORTAL_RUNNING → OTP_REQUIRED → OTP_VERIFIED → HUMAN_REVIEW → APPROVED → SUBMITTING → SUBMITTED → CERTIFICATE_READY → COMPLETED`. 

---

# 97. What happens after every API

Every mutation should follow this pattern:

```text
API request
 ↓
Authentication
 ↓
Authorization
 ↓
Resource access check
 ↓
Input validation
 ↓
Domain service
 ↓
DB transaction
 ├── data mutation
 ├── state transition
 ├── event
 └── audit
 ↓
Commit
 ↓
Queue job if necessary
 ↓
Return response
```

Not:

```text
button
 ↓
random fetch
 ↓
hope worker handles it
```

---

# 98. What happens inside every background job

```text
Job received
 ↓
Acquire application lock
 ↓
Load current state
 ↓
Verify job still legal
 ↓
Execute
 ↓
Persist result
 ↓
Emit event
 ↓
Transition state
 ↓
Release lock
```

This addresses the race-condition concern already documented in your architecture. The project specification calls for one worker per application using a Redis lock. 

---

# 99. What happens when a job fails

```text
Worker
 ↓
Exception
 ↓
Determine retryable?
      │
      ├── YES → retry
      │
      └── NO → EXCEPTION
```

Then:

```text
EXCEPTION
 ↓
workflow event
 ↓
audit
 ↓
notification
 ↓
operator UI
```

No silent failure.

That matches your build rule:

> every failure must surface to a human rather than disappearing. 

---

# 100. State-driven buttons

This should become a hard frontend rule.

### `DRAFT`

```text
Edit
Upload Documents
```

### `DOCUMENTS_PROCESSING`

```text
View Documents
```

### `EXTRACTED`

```text
Review Data
```

### `NIC_REVIEW`

```text
Generate Suggestions
Approve NIC
```

### `READY_FOR_PORTAL`

```text
Start Automation
```

### `OTP_REQUIRED`

```text
Enter OTP
```

### `HUMAN_REVIEW`

```text
Approve
Reject
```

### `EXCEPTION`

```text
Resolve
Retry
```

### `COMPLETED`

```text
View Certificate
Download
```

The frontend should never decide that an action is legal solely because a button exists.

---

# 101. The master action contract

Every button in Taxla should be represented conceptually like this:

```typescript
{
  key: "approve_nic",
  label: "Approve NIC",
  allowedStates: ["NIC_REVIEW"],
  allowedRoles: ["REVIEWER"],
  endpoint: "POST /applications/:id/nic/approve",
  transition: "NIC_REVIEW -> READY_FOR_PORTAL",
  event: "NIC_REVIEW_APPROVED",
  backgroundJob: null,
  successNavigation: "/applications/:id/automation",
  failureBehavior: "stay_on_page"
}
```

For automation:

```typescript
{
  key: "start_automation",
  label: "Start Automation",
  allowedStates: ["READY_FOR_PORTAL"],
  allowedRoles: ["OPERATOR", "REVIEWER"],
  endpoint: "POST /applications/:id/automation/start",
  transition: "READY_FOR_PORTAL -> PORTAL_RUNNING",
  event: "PORTAL_STARTED",
  backgroundJob: "browser_queue",
  successNavigation: "/applications/:id/automation",
  failureBehavior: "exception"
}
```

This is the sort of contract that keeps CoWork from inventing behavior.

---

# 102. The final end-to-end chain

Your flagship Udyam registration must be testable as one continuous journey:

```text
/login
 ↓
/dashboard
 ↓
/applications/new
 ↓
Create Application
 ↓
/applications/:id/overview
 ↓
/documents
 ↓
Upload Aadhaar
 ↓
Upload PAN
 ↓
Upload Bank Proof
 ↓
OCR worker
 ↓
Extraction worker
 ↓
Validation
 ↓
/data
 ↓
Human review
 ↓
/nic
 ↓
NIC AI
 ↓
Human NIC approval
 ↓
/workflow
 ↓
READY_FOR_PORTAL
 ↓
/automation
 ↓
Playwright
 ↓
Human Challenge
 ↓
/otp
 ↓
Submit OTP
 ↓
Browser resume
 ↓
Final review
 ↓
Approve
 ↓
Browser submission
 ↓
Submitted
 ↓
Certificate
 ↓
/artifacts
 ↓
Completed
 ↓
/timeline
```

---

# 103. This is what your CoWork implementation should be measured against

Not:

> “The dashboard looks good.”

The acceptance test is:

```text
Can the user click every action?
        ↓
Does every click call the correct API?
        ↓
Does the API enforce permission?
        ↓
Does the backend perform the correct state transition?
        ↓
Does it write workflow + audit events?
        ↓
Does it enqueue the correct worker?
        ↓
Does the worker produce a durable result?
        ↓
Does the UI update?
        ↓
Does the next legal action appear?
```

That's the **real implementation definition**.

Your existing code has the skeleton of this architecture, but currently several links in that chain are missing: workflow events aren't actually being written, workflow node persistence is incomplete, Playwright is not executing the full form flow, OCR is mocked, role enforcement isn't active, and several UI actions are dead/mocked.  

So I would add a dedicated document to your project:

# `40_PAGE_ACTION_API_STATE_JOB_CONTRACT.md`

and make it the **binding UI/backend integration specification**.

Its core schema for every action should be:

```text
PAGE
ROUTE
ROLE
PRECONDITION
UI ELEMENT
BUTTON LABEL
FRONTEND HANDLER
API METHOD
API PATH
REQUEST
RESPONSE
BACKEND SERVICE
DATABASE TABLES
STATE BEFORE
STATE AFTER
EVENT
BACKGROUND JOB
RETRY POLICY
ERROR STATE
SUCCESS UI
FAILURE UI
NEXT ROUTE
AUDIT EVENT
```

That document, together with your PRD, state machine, database schema and build rules, gives CoWork a far tighter contract than the current project has.
