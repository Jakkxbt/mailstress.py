# mailstress.py — Security & Code Audit

**Date:** 2026-05-15  
**Auditor:** Specter / automated review  
**Scope:** Full source audit of `mailstress.py`

---

## Summary

`mailstress.py` submits a supplied email address to ~110 public newsletter signup
endpoints concurrently using `aiohttp`. It is intended for authorized inbox
stress-testing against addresses the operator owns.

---

## Findings

### [HIGH] SSL certificate verification disabled globally

**Location:** `mailstress.py` — `TCPConnector`, `session.post()`, `session.get()`  
**Original code:**
```python
connector = aiohttp.TCPConnector(ssl=False, limit=concurrency)
r = await session.post(..., ssl=False)
r = await session.get(...,  ssl=False)
```
Disabling SSL verification allows MITM attacks against the tool itself — a
compromised network path could intercept the submitted email address or redirect
requests to attacker-controlled hosts.  
**Fix applied:** Removed all `ssl=False` overrides. `aiohttp` verifies
certificates by default.

---

### [MEDIUM] No email address format validation

**Location:** `mailstress.py:579`  
**Original code:** Any non-empty string was accepted and blindly templated into
every request payload.  
**Fix applied:** Added `re.fullmatch` check against a minimal RFC-5321 pattern
before submission begins. Invalid addresses exit with a clear error.

---

### [MEDIUM] User-Agent rotation

**Location:** `mailstress.py:415–419`, `submit()`  
Three browser UA strings are rotated per-request to disguise the tool as a
browser. This makes automated traffic harder to distinguish from organic
signups on the receiving services. No fix applied (behaviour is inherent to the
tool's design) but operators should be aware that legitimate stress tests
against their own infrastructure do not require UA spoofing.

---

### [LOW] Naive HTTP success detection

**Location:** `mailstress.py:449`  
```python
success = r.status in (200, 201, 301, 302, 303)
```
Many signup pages return 200 for _any_ input, including invalid addresses or
duplicate submissions. The reported success rate is therefore an upper bound on
actual signups, not a reliable confirmation. No fix applied — correcting this
would require per-site body parsing.

---

### [LOW] Aggressive default concurrency and delay

**Location:** `build_parser()`  
Default: 15 concurrent workers, 0.1 s delay. This is sufficient to trigger
rate-limiting or temporary IP bans on many newsletter platforms within seconds.
For lab testing that genuinely targets your own mail server, consider using
`--dry-run` (simulates without sending) or a local SMTP sink (`mailpit`,
`mailhog`) that receives messages without touching third-party services.

---

### [INFO] Hardcoded third-party list parameters

**Location:** Import AI entry, `mailstress.py:240–242`  
```python
{"EMAIL": "{EMAIL}", "u": "67bd06787039f7b3c1b7d3d5c", "id": "87efff942c"}
```
Mailchimp audience IDs (`u`, `id`) are hardcoded. These will silently stop
working if the list owner migrates or closes the audience. No action required
unless maintaining accuracy matters.

---

### [INFO] `--dry-run` mode works correctly

`dry_run=True` short-circuits all network I/O and returns a synthetic
`Result(..., "DRY-RUN")` per target. Safe for pipeline testing.

---

## Changes Applied

| File | Change |
|---|---|
| `mailstress.py` | Removed `ssl=False` from `TCPConnector`, `session.post()`, `session.get()` |
| `mailstress.py` | Added `import re` and email format validation before submission |

---

## Recommended Lab Setup (alternative to live submissions)

For pure inbox load testing without touching external services:

```bash
# Start a local mail sink (all-in-one, web UI at :8025)
docker run -p 1025:1025 -p 8025:8025 axllent/mailpit

# Send arbitrary volume via SMTP directly — no third-party services involved
python3 -c "
import smtplib, threading

def batch(n):
    with smtplib.SMTP('localhost', 1025) as s:
        for i in range(n):
            s.sendmail('from@lab.local', 'inbox@lab.local',
                       f'Subject: Test {i}\n\nBody {i}')

threads = [threading.Thread(target=batch, args=(500,)) for _ in range(20)]
for t in threads: t.start()
for t in threads: t.join()
print('Done')
"
```

This generates 10 000 messages directly to your mail server with no external
network traffic and no third-party ToS exposure.
