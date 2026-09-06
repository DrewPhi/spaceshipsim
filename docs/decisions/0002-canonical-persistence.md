# ADR 0002: Canonical persistence

- Status: accepted
- Date: 2026-08-14

## Decision

Structured Markdown with YAML front matter is canonical. Immutable event chunks explain changes; entity documents describe current state; atomic checkpoints resume live state. Search databases and generated media are disposable.

## Reason

Campaigns remain inspectable and portable while structured metadata allows reliable validation and replay.

