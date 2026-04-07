# Echoforge.biz Integration Spec: Accessibility Audit Module (AAM)

This spec provides the necessary REST endpoints and schemas for frontend web developers at Echoforge.biz to integrate the new Standalone Accessibility Audit offer into the public website.

## Base URL
Authentication is required via Bearer token (`Authorization: Bearer <API_TOKEN>`). 
Production API Host: `https://api.planbadmin.com`
Local/Dev API Host: `http://localhost:8000`

All routes are mounted under: `/api/audit/accessibility`

---

### 1. Initiate an Audit
`POST /api/audit/accessibility/initiate`

Starts a headless Playwright + Axe-core scan on the target URL. Due to execution time, this is an asynchronous Celery task.

**Headers:**
```http
Authorization: Bearer <API_TOKEN>
Content-Type: application/json
```

**Request Body (JSON):**
```json
{
  "url": "https://client-site.com",
  "client_id": "client@example.com", 
  "is_bundled": false, 
  "is_testing": false 
}
```

- `url` (Required): Target URL to scan. (Must include protocol `https://` or `http://`)
- `client_id` (Optional): ID or email of the purchasing client.
- `is_bundled` (Optional): Default `false`. Set to `true` ONLY if this audit is part of a larger bundled order (e.g., Marketing Audit) to prevent redundant billing triggers.
- `is_testing` (Optional): Default `false`. Set to `true` to run a free scan without triggering the internal `log_revenue` and `log_cost` counters in the platform dashboard.

**Response (202 Accepted):**
```json
{
  "status": "Accepted",
  "audit_id": "8b51d451-ce03-4632-a5dc-5df0d829910d",
  "celery_task_id": "4020d046-2bf4-45fb-a5ce-b10852e690b2"
}
```
*Note: Keep the `audit_id` to poll for the status and download the report.*

---

### 2. Poll for Status
`GET /api/audit/accessibility/status/{audit_id}`

Since scans take variable amounts of time based on site depth, poll this endpoint every 5-10 seconds to check job progress.

**Response:**
```json
{
  "status": "Completed", // Queued | Scanning | Analyzing | Completed | Failed
  "audit_id": "8b51d451-ce03-4632-a5dc-5df0d829910d"
}
```

---

### 3. Retrieve the Report Data
`GET /api/audit/accessibility/report/{audit_id}`

Only query this endpoint once the status check returns `"Completed"`.

**Response:**
```json
{
  "status": "Completed",
  "url": "https://client-site.com",
  "wcag_score": 94,
  // Note: Depending on specific schema updates, raw Axe payload and roadmap data object mappings live here.
}
```

---

### Important Business Logic Rules for Developers
1. **Financial Counters:** Firing the `/initiate` endpoint with `is_testing: false` and `is_bundled: false` will automatically register a standard standalone audit fee ($40 revenue + infrastructure compute cost) in the internal metrics. Make sure staging sites or UI design tests set `"is_testing": true`.
2. **Premium Bundle Behaviour:** Do not double-fire this API if the user purchases an "Elite Audit + Strategy" Premium Marketing package. The `marketing_audit` pipeline backend is already programmed to automatically inject an AAM worker task inline when evaluating Premium clients and embed the WCAG payload into the final PDF.