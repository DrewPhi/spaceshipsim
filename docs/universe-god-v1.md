# Universe God v1

This branch adds the first persistent deep-narrative layer without changing the deterministic simulation boundary.

## What is new

- Each encounter is expanded by a provider-neutral **Universe Architect** into a compact causal `SituationDossier`.
- Deep Discovery dossiers now explicitly contain a plausible surface interpretation, a deeper director-only interpretation, a central contradiction, a consequential choice, and a future hook.
- The Architect is instructed to create one dense causal chain rather than disconnected lore. Important facts should connect to people, testimony, evidence, questions, or consequences.
- The Architect now aims for at least two independent sensor evidence routes, including at least one route marked as a narrative contradiction. A quality pass asks the model to repair shallow dossiers that omit the required discovery shape.
- Dossiers distinguish entities, objective facts, claims, relationships, open questions, evidence routes, actor notes, and possible developments.
- Generated lore is canonical Markdown/YAML at `saves/<universe-id>/knowledge/narrative-canon.md` and survives reloads.
- NPC model calls receive only lore that NPC could know, plus public/crew information. Director-only facts are excluded.
- NPC calls are now **evidence aware**. If the crew confronts someone with evidence they actually discovered, the model receives those observations, the current discovery phase, and explicit instructions to respond to the evidence rather than ignoring or magically invalidating it.
- Contradictions do not imply lies. NPC prompts explicitly support honest error, bias, institutional narratives, incomplete records, defensiveness, uncertainty, or deception only when canon supports it.
- Important NPC actor notes are prompted to include worldview, personal stake, uncertainty/taboo, and conversational temperament so two people from the same culture do not sound like interchangeable encyclopedias.
- Ship Computer calls receive only crew-visible narrative canon and are told to distinguish observation, testimony, contradiction, and unresolved questions.
- When a player asks an NPC an unanticipated culture/history/meaning question, the architect may lazily materialize a small amount of new canon before the NPC answers.
- Lazy expansion now receives a deterministic **interest profile** based on what the player repeatedly asks about. It is instructed to deepen the same causal story instead of adding unrelated breadth.
- AI-authored evidence routes are bound to the **real deterministic sensor loop**. A clue is revealed only when the crew scans the current encounter target with an installed instrument whose domains match the route and crosses the authored scan threshold.
- A revealed clue becomes a normal Science `Observation`, a canonical `narrative_evidence_discovered` event, crew knowledge, and a persistent evidence-discovery record. Repeating the same scan cannot rediscover the same clue.
- Narrative evidence is classified as `clue`, `contradiction`, or `corroboration`. Only evidence the crew actually earns may advance the discovery state.
- Each encounter now has a persistent deterministic discovery phase: `hook -> investigation -> contradiction -> reinterpretation -> decision -> aftermath`.
- A contradiction is not promoted to a decision merely because the model wrote one. The crew must actually discover it; the decision phase normally requires multiple pieces of evidence plus an evidence-aware confrontation.
- The existing Expedition Activity Board doubles as the crew-facing discovery board. The current thread summary is updated with **KNOWN / CLAIM / CONTRADICTION / UNANSWERED / STAKES**, so the player's changing mental model is visible without adding quest markers or a second objective system.
- Meaningful discoveries and player actions can wake the Universe God to schedule coarse **off-screen actor intentions**. Those intentions persist in canon and execute later according to universe time.
- Off-screen planning now receives the discovery phase and player-interest profile so later consequences preferentially develop what the crew actually cared about.
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

## Deep Discovery playtest

For the most useful test, do **not** read the private canon until after the encounter. Play blind first.

1. Create a new **Random Expedition** universe with a live model enabled.
2. Wait for the encounter's narrative situation to be established. The Expedition Activity Board should begin showing a `DISCOVERY PHASE` summary for the active thread.
3. Form an initial theory from the public encounter and whatever the contact tells you. Ask questions in your own words rather than trying to follow a scripted sequence.
4. Watch the Activity Board. Its thread summary should evolve through labels such as:
   - `KNOWN:` evidence-backed or already crew-visible information
   - `CLAIM:` testimony that is not silently treated as objective truth
   - `CONTRADICTION:` something the crew has actually discovered that no longer fits
   - `UNANSWERED:` an unresolved question, not a required quest step
   - `STAKES:` only once the crew understands enough for consequences to be meaningful
5. In Science, scan the encounter target with different installed instruments. An evidence route only fires if the selected instrument shares one of the route's validated sensor domains and the scan reaches its required fraction.
6. Look for at least two story-relevant observations. One should ideally force you to revise the initial interpretation rather than merely giving you more detail.
7. If an NPC's earlier account no longer fits, confront them naturally, for example: `You said this structure was built after the evacuation, but our composition scan dates the inner lattice much earlier. How do you explain that?`
8. The NPC should respond specifically to the evidence and according to their own knowledge/personality. They may reconsider, distinguish two layers, become defensive, admit uncertainty, ask for the data, or reveal another source. They should not become omniscient.
9. Keep asking about whatever catches your interest. Repeated questions about naming, family, memorial practice, archives, religion, engineering, or another topic should cause lazy lore to deepen those topics rather than abruptly switching to unrelated worldbuilding.
10. Once the Activity Board reaches `DECISION`, make whatever choice the situation suggests through the existing interaction options and conversation. The game should not require that you press a special 'correct conclusion' button to understand the story.
11. Leave the system and continue travelling. The Universe God may have scheduled consequences whose delays are measured in universe time. Use time acceleration during uneventful travel if desired.
12. Watch Communications, the activity board, and previously known contacts for delayed messages, new leads, or relationship/status changes.
13. Reload the universe. Discovered evidence, generated lore, discovery phase, player-interest state, pending intentions, executed consequences, and actor memories should remain.
14. Only after playing, inspect `knowledge/narrative-canon.md`. Compare the private deeper interpretation against what you actually managed to infer.
15. Check `/api/v1/sessions/<session-id>/diagnostics`; it now includes a `deep_discovery` phase/interest summary and a structured `discovery_board` in addition to the normal narrative-canon counts.

## Acceptance test

The playability target is now deliberately simple:

1. You enter knowing almost nothing.
2. Something makes you genuinely curious.
3. You form an initial interpretation.
4. Conversation or investigation adds meaningful cultural/history/scientific context.
5. You discover physical evidence that changes the interpretation.
6. At least one person's account is revealed to be partial, biased, mistaken, evasive, or deceptive in a canon-consistent way.
7. You ask a question the source code did not anticipate and get deeper connected lore.
8. You make a choice differently because of what you learned.
9. You leave and later receive a causal consequence.
10. You reload or return and the universe remembers.
11. You can explain the encounter to another human afterward as a coherent story rather than a sequence of UI operations.

If repeated live-model Random Expedition encounters do not satisfy this, the next work should be prompt/schema/validation tuning against real play logs rather than adding another foundational subsystem.

## Architecture boundary

The model still never gets a `set_state` capability. The flow is:

`model proposes lore / evidence / intent -> schema and scope validation -> deterministic discovery/sensor/world executor -> canonical event -> persistence`

The current off-screen simulation advances only while universe time advances in a running session; it does not yet simulate elapsed wall-clock time while the host is shut down. Rich faction economies and detailed multi-system physical actor simulation remain later campaign-depth work.
