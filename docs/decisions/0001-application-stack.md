# ADR 0001: Application stack

- Status: accepted
- Date: 2026-08-14

## Decision

Use Python 3.12, FastAPI, Pydantic, asyncio, and WebSockets for the authoritative host. Use React, TypeScript, Vite, CSS, SVG, Canvas, and Web Audio for browser stations.

## Reason

The server stack supports deterministic simulation plus asynchronous AI jobs. The browser stack supports local-network devices, specialized interfaces, accessibility, and coded instrumentation without a native client installation.

