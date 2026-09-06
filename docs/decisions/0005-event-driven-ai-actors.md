# ADR 0005: Persistent event-driven AI actors

## Status

Accepted — 2026-08-14

## Context

Typed dialogue alone made contacts sound varied while leaving the surrounding game state mostly static. Calling a model on simulation ticks would be expensive, difficult to reproduce, and would blur the boundary between narrative suggestions and authoritative physics.

## Decision

NPCs persist a private actor state containing personality traits, goals, beliefs, fears, bounded memories, commitments, relationship state, and current intention. An NPC model receives only that actor's private state, its observations, public encounter context, and recent conversation. It proposes one action from a fixed vocabulary:

- hold position;
- approach;
- withdraw;
- share data;
- request an action;
- change course; or
- depart.

The deterministic simulation validates relationship and physical prerequisites, constrains invalid actions, calculates movement and deadlines, updates persistent state, and emits public and entity-private canonical events. Player projections expose observed activity, an explanation grounded in available evidence, requests, shared data, and a relationship estimate; private beliefs and memories are excluded.

The Director runs at encounter creation and selected meaningful canonical milestones, never on ordinary ticks. A Director beat may add an observable cue, adjust bounded pacing values or an existing deadline, and identify a decision. It cannot directly cause damage, movement, discovery, or equipment changes.

## Consequences

- Contacts can remember exchanges and take visible actions without giving models authority over reality.
- Model cost follows player decisions and encounter milestones instead of frame rate.
- Accepted, constrained, and private-memory changes remain auditable in the event log.
- Provider failure still falls back to deterministic actor behavior and does not stop simulation.
- New actor actions require an explicit validator and projection policy before entering the vocabulary.
