# Universe God v1

This branch adds the first persistent deep-narrative layer without changing the deterministic simulation boundary.

## What is new

- Each encounter is expanded by a provider-neutral **Universe Architect** into a compact causal `SituationDossier`.
- Dossiers distinguish entities, objective facts, claims, relationships, open questions, evidence routes, actor notes, and possible developments.
- Generated lore is canonical Markdown/YAML at `saves/<universe-id>/knowledge/narrative-canon.md` and survives reloads.
- NPC model calls receive only lore that NPC could know, plus public/crew information. Director-only facts are excluded.
- Ship Computer calls receive only crew-visible narrative canon.
- When a player asks an NPC an unanticipated culture/history/meaning question, the architect may lazily materialize a small amount of new canon before the NPC answers.
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

Optionally point only the Universe Architect/lore-expansion role at a different model:

```bash
export SPACE_CREW_NARRATIVE_BASE_URL=http://127.0.0.1:11434/v1
export SPACE_CREW_NARRATIVE_MODEL=qwen3:14b
export SPACE_CREW_NARRATIVE_PROVIDER=ollama
```

If these `SPACE_CREW_NARRATIVE_*` variables are absent, the main configured model is reused. No gameplay code depends on a particular model vendor or model name.

## First playtest

1. Create a new **Random Expedition** universe with a live model enabled.
2. Wait a few seconds after encounter creation for the Universe Architect task.
3. Open the save directory and inspect `knowledge/narrative-canon.md`. It should contain a situation premise, persistent entities/facts/questions, and, where appropriate, evidence routes.
4. If the encounter contains an NPC, ask questions that were not anticipated by the UI, for example:
   - `Why is that custom important to your people?`
   - `Who disagrees with that version of your history?`
   - `What does that name mean?`
   - `How did this practice begin?`
5. Ask a follow-up about an answer. The canon file should gain a **Lazy lore expansions** section rather than replacing the original facts.
6. Reload the universe and ask about the same subject again. Previously materialized lore should still constrain the actor.
7. Check `/api/v1/sessions/<session-id>/diagnostics`; `narrative_canon` reports situation/entity/fact/question/expansion counts and `narrative_provider` reports the model used for architecture.

## Important current limit

Universe God v1 establishes the narrative substrate and deep conversational continuity. Generated `evidence` entries are persisted and restricted to domains the ship actually has, but they are not yet converted automatically into new deterministic scan observations. The next implementation slice should bind those evidence routes to the existing sensor pipeline and add scheduled off-screen world intentions/consequences.
