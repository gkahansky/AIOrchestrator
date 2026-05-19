# Prompt: Add URL/Email Domain-Match Validation to Accessibility Audit Order Form

## Context

We need to prevent orders where the customer's email address does not belong to
the same domain as the website they're submitting for an audit. This is an
ownership/trust check — a customer at `jane@gmail.com` should not be able to
order an audit for `acme.com`.

---

## The Rule

When a user submits the accessibility audit order form, if both a website URL
and a contact email are provided, the domain extracted from the URL must equal
the domain extracted from the email. If they don't match, block the submission
with a clear error message.

This applies to **both** sample orders and full paid orders.

---

## Domain Extraction Logic

**From the URL:**
1. Parse the URL (e.g. `new URL(rawUrl)` in JS, or `urllib.parse.urlparse` in Python)
2. Extract the hostname (e.g. `"www.acme.com"`)
3. Strip a leading `www.` prefix → `"acme.com"`
4. Lowercase the result

**From the email:**
1. Split on `"@"`
2. Take the second part → `"acme.com"`
3. Lowercase the result

**Match condition:** `urlDomain === emailDomain` — exact string equality, case-insensitive.

---

## Where to Add It

### 1. Client-side (JavaScript / TypeScript form)

Add these two helper functions and the guard inside the submit handler,
**before** the API call fires:

```typescript
function getUrlDomain(rawUrl: string): string {
  try {
    const host = new URL(rawUrl).hostname
    return host.replace(/^www\./, "").toLowerCase()
  } catch {
    return ""
  }
}

function getEmailDomain(email: string): string {
  const parts = email.split("@")
  return parts.length === 2 ? parts[1].toLowerCase() : ""
}

// Inside handleSubmit / onSubmit — before the API call:
if (email) {
  const urlDomain = getUrlDomain(websiteUrl)
  const emailDomain = getEmailDomain(email)
  if (urlDomain && emailDomain && urlDomain !== emailDomain) {
    setError(
      `Your email domain "${emailDomain}" must match the website domain "${urlDomain}". ` +
      "Please use an email address belonging to the website you're submitting."
    )
    return
  }
}
```

Show the error inline near the email field (not just a toast — it must be
visible without the user having to scroll or look away from the form).

Update the email field's label or helper text to hint at this requirement:

> *"Contact Email — must use the same domain as the website above
> (e.g. you@acme.com for acme.com)"*

### 2. Server-side (API endpoint / backend validation)

In the endpoint that receives the accessibility audit order (e.g. a POST to
`/api/audit` or `/api/order`), add validation **before** inserting the record
or triggering the job:

```python
from urllib.parse import urlparse

def _domain_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.").lower()

def _domain_from_email(email: str) -> str:
    parts = email.split("@", 1)
    return parts[1].lower() if len(parts) == 2 else ""

# Inside the request handler / validator:
if client_email:
    url_domain = _domain_from_url(website_url)
    email_domain = _domain_from_email(client_email)
    if url_domain and email_domain and url_domain != email_domain:
        raise ValidationError(
            f"Email domain '{email_domain}' must match the website domain "
            f"'{url_domain}'. The audit can only be ordered for a domain "
            "the customer controls."
        )
```

Return **HTTP 422 Unprocessable Entity** with a JSON body like:

```json
{
  "detail": "Email domain 'gmail.com' must match the website domain 'acme.com'. The audit can only be ordered for a domain the customer controls."
}
```

---

## Edge Cases — Handle Gracefully (Do Not Block)

| Case | Behaviour |
|---|---|
| Email field is empty / not provided | Skip the check — email is optional |
| URL cannot be parsed | Skip the check — don't block on malformed URLs |
| Email has no `@` | Skip the check — browser `type="email"` catches this first |
| Subdomains (`app.acme.com` vs `acme.com`) | **Block** — only exact domain match is accepted |

---

## Test Scenarios

| Website URL | Email | Expected |
|---|---|---|
| `https://acme.com/pricing` | `jane@acme.com` | ✅ Allow |
| `https://www.acme.com` | `jane@acme.com` | ✅ Allow (`www.` stripped) |
| `https://acme.com` | `jane@gmail.com` | ❌ Block — domain mismatch |
| `https://acme.com` | *(no email)* | ✅ Allow — email is optional |
| `https://app.acme.com` | `jane@acme.com` | ❌ Block — subdomain ≠ root domain |

---

## Implementation Notes

- Implement **both** client-side and server-side checks. Client-side gives instant
  feedback; server-side is the enforceable gate.
- The check runs on the **same fields used for delivery** — the URL the audit runs
  against, and the email the report is sent to.
- Do not add this check to the admin/internal ordering UI — it is only required
  on the public-facing echoforge.biz order form where customers self-serve.
