# Minimal Playtest Guide

This is the stopping point for the first playable build. Later roadmap features—speech, image reconstruction, generated code, deep civilizations, and public hosting—are intentionally absent.

## Start the host

```bash
UV_CACHE_DIR=.uv-cache uv sync --extra dev
npm install
npm run build
UV_CACHE_DIR=.uv-cache uv run space-sim-crew
```

Open `http://localhost:8000`. Other devices on the same local network use `http://<host-ip>:8000`.

No AI setup is required. The deterministic fallback provides Director details, Ship Computer answers, and contact responses. To use another model, configure the environment variables documented in `README.md`.

To run the installed local hybrid AI instead, use `./scripts/run-local-ai.sh`.

## Solo playtest

1. Create a universe, ship, and character.
2. Join the **Integrated** station.
3. Read the current situation and choose its target in Science.
4. Begin a scan. After the first bearing, use **Execute 2,000 km baseline** and watch the purple ship move in the fixed baseline frame while the autopilot accelerates and brakes.
5. Scan again and confirm that the crossed bearings produce a probability region and intercept heading.
6. In Communications, acquire the four-channel signal and run the structure test. Inspect the waveform and spectrogram.
7. If the test reports correlated contamination, open PCA. Click a gap between eigenvalues, reconstruct each side, and rerun the structure test. Confirm that the workflow distinguishes preserved structure from an unhelpful reconstruction.
8. Try an incorrect demodulator. Confirm that it reports frame-lock failure and that interpretation returns nonsense rather than a message.
9. Try the other demodulators until a stable symbol frame appears, then run adaptive interpretation.
10. Optionally reply on the recovered channel and confirm that a returned acknowledgment appears in the transcript.
11. Confirm that **Conclude investigation** remained unavailable until localization and interpretation were complete, and that concluding records the measured message while leaving unmeasured identity and origin unresolved.
12. Optionally route the PCA reconstruction to Science and open **Advanced residual-state analysis**. Diffusion maps are a physical/instrumental residual-analysis tool, not part of message decoding.
13. Reallocate power. Confirm that additional sensor power accelerates the scan and propulsion power changes maneuvering.
14. If a vessel is present, send different kinds of messages and observe disposition, posture, and deadline changes.
15. Resolve the encounter, recover available salvage, install it, and travel to a neighboring system.
16. Continue through several systems, then stop the host, restart it, and load the same universe.

Expected result: location, systems, messages, discoveries, damage, cargo, and installed capabilities remain. There is no final destination or campaign-complete screen.

## Crew playtest

Use a separate browser or device for each participant. Load the same universe and create a distinct crew character before joining.

Recommended assignments:

| Players | Assignment |
|---:|---|
| 2 | Integrated consoles, with one leading Flight/Command and one leading Science/Engineering/Communications |
| 3 | Command/Flight, Engineering/Tactical, Science/Communications |
| 4 | Command, Flight/Tactical, Engineering, Science/Communications |
| 5 | Command, Flight/Tactical, Engineering, Science, Communications |
| 6 | Command, Flight, Engineering, Science, Communications, Tactical |

The current UI provides Integrated and dedicated station screens. For crews of two through five, use Integrated stations when a player needs access to combined responsibilities; automatic composite layouts remain an unchecked MPP item in `PROJECT_PLAN.md`.

During the playtest:

- Do not read another player's screen unless testing reconnection.
- Report observations verbally, including confidence and repeated periods.
- Let Command decide priorities from reports rather than inspecting every station.
- Disconnect one station for at least five seconds, reconnect, and confirm its current snapshot returns.
- Try both cooperation and escalation with a contact.
- Record any station that lacks a meaningful decision for five minutes.

## What to evaluate

- Did three separate readings lead the crew to notice a shared cause?
- Did Engineering choices create useful tradeoffs?
- Did a hidden deadline create urgency without feeling arbitrary?
- Could every player explain what their controls affected?
- Could Communications explain why it selected one side of the PCA partition?
- Could Science explain what proximity, time linkage, and isolated points meant in the diffusion embedding?
- Did the Ship Computer help without revealing an answer the crew had not measured?
- Did the crew want to travel to another system?
- Which responsibilities should be combined for each crew size?

Record defects and playtest notes as GitHub issues once the repository can be connected. Do not mark the human-playtest checklist gates complete until an actual crew has run this guide.
