# ADR 0004: AI provider boundary

- Status: accepted
- Date: 2026-08-14

## Decision

All models implement a capability-reporting provider interface. The host constructs role-specific tasks and validates typed proposals. A deterministic provider guarantees offline play. No provider receives direct save or simulation mutation authority.

## Reason

The campaign must work with laptop-scale local models, stronger local hardware, hosted endpoints, or no live language model without changing canon or game rules.

