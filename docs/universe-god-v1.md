# Universe God v1

This branch adds the first persistent deep-narrative layer without changing the deterministic simulation boundary.

## What is new

- Each encounter is expanded by a provider-neutral **Universe Architect** into a compact causal `SituationDossier`.
- Dossiers distinguish entities, objective facts, claims, relationships, open questions, evidence routes, actor notes, and possible developments.
- Generated lore is canonical Markdown/YAML at `saves/<universe-id>/knowledge/narrative-canon.md` and survives reloads.
- NPC model calls receive only lore that NPC could know, plus public/crew information. Director-only facts are excluded.
- Ship Computer calls receive only crew-visible narrative canon.
- When a player asks an NPC an unanticipated culture/history/meaning question, the architect may lazily materialize a small amount of new canon before the NPC answers.
- AI-authored evidence routes are now bound to the **real deterministic sensor loop**. A clue is revealed only when the crew scans the current encounter target with an installed instrument whose domains match the route and crosses the authored scan threshold.
- A revealed clue becomes a normal Science `Observation`, a canonical `narrative_evidence_discovered` event, crew knowledge, and a persistent evidence-discovery record. Repeating the same scan cannot rediscover the same clue.
- Meaningful discoveries and player actions can wake the Universe God to schedule coarse **off-screen actor intentions**. Those intentions persist in canon and execute later according to universe time.
- Off-screen consequences are intentionally bounded to delayed messages, new leads, relationship shifts, new claims/facts, and coarse social/activity status changes. They cannot directly edit coordinates, hull, damage, cargo, power, resources, or other physical state.
- Existing physics, sensors, deadlines, equipment, damage, movement, and permissions remain deterministic and server-validated.

## Model configuration

The simple setup remains unchanged. One model can run everything:

```bash
export SPACE_CREW_AI_BASE_URL=http://127.0.0.1:11434/v1
export SPACE_CREW_AI_MODEL=qwen3:8b
export SPACE_CREW_AI_PROVIDER=ollama
export SPACE_CREW_AI_MAX_TOKENS=1200
uv run space-sim-crew
```

Any OpenAI-compatible endpoint can be used instead.

Optionally point only the Universe Architect/lore-expansion/world-planning role at a different model:

```bash
export SPACE_CREW_NARRATIVE_BASE_URL=http://127.0.0.1:11434/v1
export SPACE_CREW_NARRATIVE_MODEL=qwen3:14b
export SPACE_CREW_NARRATIVE_PROVIDER=ollama
```

If these `SPACE_CREW_NARRATIVE_*` variables are absent, the main configured model is reused. No gameplay code depends on a particular model vendor or model name.

## Deep-narrative playtest

1. Create a new **Random Expedition** universe with a live model enabled.
2. After encounter creation, inspect `knowledge/narrative-canon.md`. It should contain a situation premise, persistent entities/facts/questions and, where appropriate, evidence routes and scheduled intentions.
3. In Science, scan the encounter target with different installed instruments. An evidence route only fires if the selected instrument shares one of the route's validated sensor domains and the scan reaches its required fraction.
4. Watch for story-relevant Science observations rather than generic completion text. The canon file should add an **Evidence actually discovered** section after a successful clue.
5. If the encounter contains an NPC, ask questions that were not anticipated by the UI, for example:
   - `Why is that custom important to your people?`
   - `Who disagrees with that version of your history?`
   - `What does that name mean?`
   - `How did this practice begin?`
6. Ask follow-ups. The canon file should gain **Lazy lore expansions** rather than replacing original facts.
7. Make a meaningful choice or discovery, then leave the system and continue travelling. The Universe God may have scheduled consequences whose delays are measured in universe time. Use time acceleration during uneventful travel if desired.
8. Watch Communications, the activity board, and previously known contacts for delayed messages, new leads, or relationship/status changes. `narrative-canon.md` records scheduled and executed intentions.
9. Reload the universe. Discovered evidence, generated lore, pending intentions, executed consequences, and actor memories should remain.
10. Check `/api/v1/sessions/<session-id>/diagnostics`; `narrative_canon` now reports evidence-discovery and scheduled/executed-intent counts in addition to situation/entity/fact/question/expansion counts.

## Architecture boundary

The model still never gets a `set_state` capability. The flow is:

`model proposes lore / evidence / intent -> schema and scope validation -> deterministic scan or world executor -> canonical event -> persistence`

The current off-screen simulation advances only while universe time advances in a running session; it does not yet simulate elapsed wall-clock time while the host is shut down. The next campaign-depth work can broaden the same architecture to long-lived factions, multi-system movement/economics, and richer evidence bound to specific generated objects without weakening the simulation boundary.
