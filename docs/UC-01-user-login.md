# UC-01 · User Login

## Problem

The GovCA portal at `https://www.govca.rw/apply/searchIndvdlProductList.sg` requires applicants to authenticate before accessing the digital certificate application. Currently:

- There is no client-side validation before the form submits, causing unnecessary server round-trips on obvious input errors.
- Failed logins return a generic error with no actionable guidance.
- Users who forget their password have no clear route; the forgot-password page (`/reissue/stepIndvdlReisue.sg`) is buried in the navigation.
- There is no session timeout warning, so users lose form data silently.

## Solution

A login middleware module that:

1. Validates National ID format and password presence client-side before submission.
2. Calls the GovCA authentication endpoint and handles the response.
3. On success, creates a server-side session and redirects to the application dashboard.
4. On failure, displays the specific error (wrong ID, wrong password, account locked) and offers the forgot-password link prominently.
5. Issues a session-timeout warning at 25 minutes of inactivity.

## How To

### Step 1 — Collect credentials
The user visits `/apply/searchIndvdlProductList.sg`, clicks a certificate type (e.g. Local Individual), and is prompted to log in.

### Step 2 — Client-side validation
The login form checks:
- National ID: 16-digit numeric format (Rwanda NID standard).
- Password: not empty, minimum 8 characters.

### Step 3 — Submit to auth endpoint
```
POST /auth/login
Content-Type: application/json
{ "national_id": "1199...", "password": "..." }
```

### Step 4 — Handle response
- `200 OK` → create session token, redirect to `/document/stepIndvdlDocument.sg`.
- `401 Unauthorized` → show "Incorrect ID or password" + link to `/reissue/stepIndvdlReisue.sg`.
- `423 Locked` → show "Account locked. Contact GovCA helpdesk."

### Step 5 — Session lifecycle
- Session TTL: 30 minutes (sliding).
- Warning shown at T-5 minutes.
- On expiry, redirect to login with message: "Session expired. Please log in again."

## Outcome

- Users authenticate in under 3 seconds on a standard connection.
- Wrong-credential errors are specific and actionable.
- Password-reset path is surfaced immediately on first failure.
- No session data is lost without a warning.

## Actors

| Actor | Role |
|-------|------|
| Applicant | Primary — submits credentials |
| GovCA Auth Service | System — validates credentials, issues token |

## Pre-conditions
- Applicant has a registered GovCA account.
- Portal is reachable at `https://www.govca.rw`.

## Post-conditions
- Session token stored server-side.
- User redirected to document upload step.
