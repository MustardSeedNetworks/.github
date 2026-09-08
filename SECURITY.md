# Security Policy

This policy applies to every Mustard Seed Networks repository that does not
carry its own `SECURITY.md`. Product repos (seed, stem, niac-go, trellis)
have their own, which take precedence.

## Supported versions

Until a project reaches 1.0, only the **latest released version** receives
security fixes. Older 0.x versions stay on the repo for reference but are not
patched — upgrade to the current minor.

| Version         | Supported          |
| --------------- | ------------------ |
| Latest (`main`) | :white_check_mark: |
| Older 0.x       | :x:                |

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.**

Use one of these private channels:

1. **GitHub Security Advisories (preferred):** open a draft advisory from the
   affected repository's *Security* tab. It is visible only to maintainers and
   you, with a built-in audit trail and CVE coordination workflow.
2. **Email:** `kris.armstrong@icloud.com` with the subject
   `[SECURITY] <repository name>`.

Include in your report:

- A description of the vulnerability and the affected component(s).
- Steps to reproduce, ideally with a minimal proof-of-concept.
- The version / commit you tested against.
- The potential impact (for example unauthenticated RCE, information
  disclosure, denial of service).
- A suggested fix or mitigation, if you have one.

## What to expect

- **Acknowledgment** within 2 business days.
- **Triage** with a severity assessment within 7 business days.
- **Fix or mitigation** in the next release for High and Critical findings,
  with a coordinated disclosure date agreed with you.
- **Credit** in the release notes and advisory unless you prefer to stay
  anonymous.
