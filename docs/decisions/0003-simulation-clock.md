# ADR 0003: Simulation clock

- Status: accepted
- Date: 2026-08-14

## Decision

Run one authoritative fixed-target loop at 20 Hz. Support 1x, 5x, 20x, and 100x time scales, denying acceleration during unsafe situations.

## Reason

Twenty updates per second are sufficient for tactical console play while leaving resources for local inference and multiple browser clients.

