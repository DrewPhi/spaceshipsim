# Space Simulation Crew — Master Project Blueprint

> Status: planning baseline  
> Product identity: original cooperative science-fiction simulation  
> Initial deployment: trusted local network  
> Canonical persistence: structured Markdown  
> Primary experience: endless exploration, discovery, first contact, and crew coordination

This document is the authoritative product specification, technical design, and implementation checklist. A checkbox is complete only when its acceptance criteria and tests pass. Changes to a foundational rule require an Architecture Decision Record (ADR) in `docs/decisions/` and an update to this document.

Player-experience priorities are stated in [main_point_of_game.md](main_point_of_game.md).
Use that document when deciding what to build next: the central reward is an
unfolding, player-directed discovery of AI-generated phenomena, civilizations,
histories, and lore. Working controls and completed checklists alone do not meet
that goal.

## 1. Product definition

Space Simulation Crew is an original cooperative game in which one or more people operate a deep-space vessel through specialized browser-based stations. Each person sees only the information their assigned station and character could obtain. The crew must communicate, form hypotheses, configure the ship, and make decisions while a persistent universe continues to evolve.

The campaign has no scripted ending. New systems and deeper detail are generated lazily as the crew explores. Generated content becomes permanent canon only after it passes deterministic validation. The AI supplies meaning, dialogue, interpretation, and proposals; ordinary code remains authoritative over physical state, permissions, persistence, and game rules.

### 1.1 Product pillars

- **Crew communication is the main mechanic.** Important situations produce different partial observations at different stations.
- **Discovery replaces quest-marker play.** Players observe, hypothesize, experiment, communicate, decide, and live with the consequences.
- **The universe remembers.** People, ships, artifacts, claims, evidence, discoveries, mistakes, and consequences persist.
- **Knowledge is progression.** A translation corpus, scientific technique, reliable map, or diplomatic relationship can be as valuable as equipment.
- **The ship is a character.** Damage, repairs, modifications, invented instruments, and salvaged systems accumulate into a unique vessel.
- **AI enriches a real simulation.** Models never directly overwrite physical truth or canonical saves.
- **Ordinary space exists.** The Director is allowed to produce no event; novelty and danger are deliberately paced.
- **The presentation is original.** Do not copy names, lore, terminology, iconography, sound design, uniforms, vessel silhouettes, or console layouts from an existing franchise.

### 1.2 Non-goals for the first release

- Walking through a rendered 3D ship or planetary environment.
- Photorealistic continuous visuals.
- Strict orbital-mechanics or relativistic simulation.
- A pre-authored main campaign with a final boss or ending.
- Public matchmaking, accounts, monetization, or an official hosted service.
- Training a new language, speech, or image model.
- Allowing generated code unrestricted operating-system, network, or filesystem access.

## 2. Foundational laws

These rules are implementation invariants.

1. **The simulation owns reality.** Position, motion, power, heat, damage, range, detection, resources, deadlines, and collisions are calculated by deterministic code.
2. **Models submit proposals.** An AI response cannot become reality until schema, authorization, continuity, capability, and physics validation succeeds.
3. **Events change canon.** Every consequential committed change creates an immutable canonical event.
4. **Sensors reveal projections.** A station receives observations derived from truth, sensor capability, power, distance, interference, damage, and operator actions.
5. **Secrets are excluded, not merely hidden by instruction.** A player-facing model call never receives unauthorized truth.
6. **Claims are not facts.** Testimony, mythology, propaganda, translations, and player hypotheses retain provenance and confidence.
7. **Absence is evidence.** A sufficiently complete scan records what it would have detected but did not.
8. **Committed canon is never silently rewritten.** Revelations add facts or discredit claims; they do not edit history into a new version.
9. **Unknown may remain unknown.** A mystery does not require a generated answer until causality or evidence makes one necessary.
10. **AI failure remains in fiction.** Timeouts become analysis, translation, or communication delays; the simulation continues.
11. **Generated capabilities are least-privileged.** Prefer built-in actions, then declarative composition, then approved sandboxed scripts.
12. **Saves are inspectable.** Persistent state is represented by structured Markdown. Any database index is disposable and rebuildable.
13. **The active region is detailed; distant space is coarse.** The game never attempts to tick an entire galaxy in real time.
14. **Player actions matter.** Timers, NPC intentions, discoveries, and future history respond to player choices.
15. **No model is mandatory.** AI integrations implement a shared provider contract and expose their capabilities at runtime.

## 3. Minimal Playable Product (MPP)

The MPP is not a short scripted demo. It is the smallest complete **endless expedition**: players can continue moving through newly generated space, encountering situations, changing their ship, and preserving canon indefinitely. Its mechanic vocabulary is intentionally bounded even though the generated combinations and lore are unbounded.

### 3.1 MPP player loop

1. Create or load a universe.
2. Create or select a character and ship.
3. Host a session and join from one or more browsers.
4. Assign, merge, or automate station responsibilities.
5. Inspect local conditions and select a destination or investigation target.
6. Travel and maneuver in real time or accelerate uneventful travel.
7. Detect partial evidence through station-specific sensors.
8. Coordinate scans, experiments, power, communications, and movement.
9. Respond to AI-directed NPC intentions and hidden deadlines.
10. Resolve or leave the situation through investigation, diplomacy, retreat, trade, salvage, or combat.
11. Commit discoveries, claims, relationships, damage, and upgrades to canon.
12. Choose another destination and repeat without a scripted endpoint.

### 3.2 Included in the MPP

- [x] Universe creation from a stable seed.
- [ ] Character creation from a written backstory or AI-assisted draft.
- [ ] Small, medium, and large starter-ship templates appropriate to crew size.
- [x] One-to-six-player session support, with no hard-coded architectural client limit.
- [x] Six core responsibility groups: Command, Flight, Engineering, Science, Communications, and Tactical.
- [ ] Integrated solo console plus merged layouts for crews of two through five.
- [ ] Browser lobby, station assignment, readiness, join codes, reconnect, and reassignment.
- [x] Authoritative 20 Hz server simulation.
- [ ] Cinematic tactical steering, intercepts, collision avoidance, orbit, retreat, and long-range transit.
- [x] Reactor, power allocation, heat, shields, hull, propulsion, sensors, communications, and at least one weapon/countermeasure pair.
- [x] Environmental conditions that affect multiple stations differently.
- [x] Deterministic sensor uncertainty and information asymmetry.
- [x] Lazy generation of connected systems and their basic celestial structure.
- [x] At least six reusable situation families: ordinary survey, artificial signal, damaged vessel, environmental hazard, disputed boundary, and ancient site.
- [x] Provider-neutral AI Director producing validated structured proposals.
- [x] AI-controlled NPC conversations through typed Communications messages.
- [x] Ship Computer questions based only on ship state and crew-accessible knowledge.
- [x] Hidden clocks that change in response to player behavior.
- [ ] One situation that supports investigation, diplomacy, retreat, and combat outcomes.
- [x] Salvage, cargo, installation, and one permanent capability upgrade.
- [ ] Canonical Markdown saves, event history, checkpoints, crash recovery, and reload.
- [x] Disposable SQLite search index rebuilt entirely from Markdown.
- [x] Model timeout, malformed-output, and unavailable-provider fallbacks.
- [x] Diagnostics showing simulation health, clients, provider status, queue depth, and save integrity.

### 3.3 Explicitly deferred beyond the MPP

- [ ] Spoken alien transmissions and procedural audio processing.
- [ ] Generated viewscreen reconstructions.
- [ ] Arbitrary invented instruments beyond the shipped declarative component vocabulary.
- [ ] Sandboxed generated scripts.
- [ ] Complex faction economies and long-running wars.
- [ ] Multiple simultaneously active player ships.
- [ ] Character aging, inheritance, permanent death, and historical eras.
- [ ] Public internet hosting and account systems.

### 3.4 MPP acceptance gates

- [x] A solo player can create a universe and continue exploring without selecting a scripted campaign.
- [ ] Four- and six-player crews can finish at least one multi-station situation and proceed to another system.
- [x] Ten consecutively generated systems have stable IDs and preserve their state when revisited.
- [x] At least one physical cause produces correlated observations on three different stations.
- [x] Engineering power changes measurably affect Flight and Science.
- [x] A Communications message can alter an NPC intention and cancel, extend, shorten, or replace a hidden deadline.
- [x] A recovered component remains installed after server restart.
- [x] An eight-hour automated soak completes without a blocked simulation loop or corrupted canonical files.
- [x] Disconnecting and reconnecting a client restores the correct authorized station snapshot.
- [x] Disabling the AI provider mid-encounter does not stop flight, damage, timers, saves, or player controls.
- [x] A secrecy test proves that player-facing prompts and payloads contain no Director-only facts.
- [ ] Replaying a seed plus its event log reconstructs equivalent canonical state.

## 4. Crew scaling and station responsibilities

Ships describe responsibilities and capabilities independently from screen layouts. A session composes those responsibilities into a layout for the current crew.

### 4.1 Default layouts

| Humans | Default assignment |
|---:|---|
| 1 | Integrated Command: simplified Flight, Systems, Discovery, Contact, and Defense; routine operations automated |
| 2 | Command/Flight/Defense and Engineering/Science/Communications |
| 3 | Command/Flight, Engineering/Defense, Science/Communications |
| 4 | Command, Flight/Defense, Engineering, Science/Communications |
| 5 | Command, Flight/Defense, Engineering, Science, Communications |
| 6 | Command, Flight, Engineering, Science, Communications, Tactical |
| 7+ | Six core stations plus Medical, Research, Intelligence, Damage Control, Flight Operations, drones, or away teams |

Players may override these defaults. A persistent NPC officer or ship automation may hold an unassigned responsibility. Automated responsibilities report through the Ship Computer, respond more slowly than an attentive human, and never receive secret information.

### 4.2 Command

Primary duties:

- Set priorities and alert posture.
- Maintain the mission and decision log.
- View a deliberately broad but low-detail strategic display.
- Request reports and designate shared targets.
- Control safe time acceleration.
- Approve restricted actions such as weapons release, dangerous experiments, alien-system installation, abandoning ship, and irreversible loss settings.

Command must not receive an omniscient interface. Its play comes from coordination, prioritization, authorization, and decisions.

### 4.3 Flight

Primary duties:

- Heading, throttle, maneuvering, intercept courses, avoidance, orbit, docking, and long-range route selection.
- Estimate arrival, fuel/energy use, drive stress, and navigational uncertainty.
- Deploy and route probes, shuttles, and remote vehicles when installed.
- Build spatial maps and identify safe approach geometry.

Flight remains occupied during investigations through orbital operations, probe control, station keeping, route planning, and hazard tracking.

### 4.4 Engineering

Primary duties:

- Reactor control, batteries, buses, power priority, heat, coolant, drive condition, repairs, and damage isolation.
- Fabrication, cargo integration, equipment installation, compatibility adapters, and reverse engineering.
- Configure cross-system experiments requested by Science or Flight.
- Track temporary workarounds, component wear, and repair teams.

### 4.5 Science

Primary duties:

- Select targets, instruments, resolution, integration time, and scan mode.
- Analyze spectra, particles, fields, composition, life, geology, artifacts, and anomalies.
- Record hypotheses separately from confirmed facts.
- Correlate readings across instruments and request experimental configurations.
- Search ship capabilities by describing a desired measurement.

### 4.6 Communications

Primary duties:

- Detect, isolate, route, record, decode, and classify signals.
- Build language corpora and test phonology, grammar, speaker, context, and cultural hypotheses.
- Type outgoing messages and manage translation confidence.
- Maintain diplomatic history, public claims, known taboos, authentication, and encryption.
- Privately receive audio and explicitly route it to selected stations or shared speakers.

### 4.7 Tactical

Primary duties:

- Identify threats, track contacts, classify capabilities, control shields, and propose weapons release.
- Operate countermeasures, point defense, drones, boarding defense, and internal security.
- Evaluate firing geometry, collateral risk, legal/command authorization, and escape windows.
- Support noncombat investigations through remote platforms and controlled demolition.

### 4.8 Complete station instrument and control catalogue

Names in this catalogue describe real functions. A control must expose the measurement, transformation, physical action, or authorization it performs; unexplained fictional labels are not acceptable. Each analysis operation keeps its parameters, input data, output data, uncertainty, and provenance.

#### Shared display conventions

- [x] Local and system-scale position model with known bodies, ship position, heading, measured bearing lines, and a source probability region.
- [x] Text-mode guidance that states missing prerequisites and the next useful action.
- [x] Communications owns acquisition and PCA separation; Science receives a dataset only through an explicit canonical handoff and owns physical classification and diffusion-map analysis.
- [x] AI Director may propose a bounded numerical signal recipe; deterministic trusted code validates it and synthesizes reproducible multichannel samples without executing generated code.
- [x] Initial signal laboratory provides a waveform, Hann-window spectrogram, PCA scree curve/loadings, clickable eigenvalue partition, explicit high/low-variance side reconstruction, diffusion eigenvalues, tunable kernel bandwidth/time/neighbors, time-linked embedding, outlier diagnostics, and neighbor reconstruction.
- [x] Acquired baseband signals provide clearly labeled, frequency-shifted audible monitoring for raw and PCA-reconstructed data, with stop controls and no implication that telemetry is decoded speech.
- [x] The console provides master caution and warning annunciators, acknowledge behavior, severity-specific tones, optional simulation-clock ticking, mute controls, and reduced-motion-safe visual states.
- [x] Stable symbol frames feed an explicit Universal Translator stage with input rejection, protocol diagnostics, confidence, plain-language semantic rendering, and a required translated reply for contact establishment.
- [x] Artificial-signal deadline expiry commits a detailed failed-contact event, moves the encounter out of active state, preserves any acquired recording for post-incident analysis, and presents a persistent signal-lost outcome with a next action.
- [x] Signal loss automatically closes waveform and derived-data panels, clearly separates retained recordings from live reception, and lets Communications reopen or clear the post-incident workspace.
- [x] PCA processing is reversible: returning to raw data preserves the recording while invalidating PCA-dependent structure, demodulation, translation, Science handoff, and classification products.
- [x] Signal encounters expose a bounded center-frequency observation; the receiver automatically locks and records detected traffic, Communications manually tunes only the reply transmitter, and a validated typed reply receives a safe AI-generated translated response through the provider contract.
- [x] AI-backed Ship Computer, vessel transmission, and translated-signal requests expose waiting, received, and failed UI states.
- [x] The system map plots radar-authorized vessel contacts with range, bearing, confidence, and tracked/hostile state.
- [x] Flight and Command can execute a deterministic emergency warp to a neighboring system, closing the current encounter while adding heat and dropping defensive fields.
- [x] Science instruments use purpose-first player labels—Composition and Temperature, Radiation Hazard, Signal Direction, and Vessel Systems and Weapons—with valid-target and expected-result guidance shown before scanning.
- [x] Universe creation offers a Friendly Contact Test preset with automatic carrier reception, a pretranslated greeting, a two-hour pre-contact window, a visible vessel, and unlimited repeated AI-backed translated exchanges after contact.
- [x] Addressed vessel and artificial-source carriers are detected, frequency-labeled, locked, and recorded automatically; manual frequency entry is required only for transmission.
- [x] AI-backed Ship Computer, vessel transmission, and translated-signal requests expose waiting, received, and failed UI states.
- [x] The system map plots radar-authorized vessel contacts with range, bearing, confidence, and tracked/hostile state.
- [x] Flight and Command can execute a deterministic emergency warp to a neighboring system, closing the current encounter while adding heat and dropping defensive fields.
- [x] Artificial-signal workflow exposes detection/localization/acquisition/structure/separation/demodulation/interpretation/reply/conclusion status and the next required action.
- [x] Communications can run a structure test, receive an explicit contamination result, try named demodulators, observe stable or failed framing, receive nonsense from invalid interpretation, recover a measured message, and transmit a reply with acknowledgment.
- [x] Diffusion maps are optional advanced Science analysis for residual physical/instrumental structure and never gate ordinary message recovery.
- [x] Signal acquisition, transformations, handoff, parameters, and classification are preserved in an operator/time-stamped processing log.
- [ ] Every plot labels axes, units, sample interval, instrument, calibration state, and uncertainty.
- [x] Raw data remains available after processing; transformations create derived datasets rather than overwriting samples.
- [ ] Warning lamps distinguish advisory, caution, and immediate hazard states and identify the measurement that triggered them.
- [ ] Controls are disabled with a plain-language prerequisite instead of silently doing nothing.
- [ ] Color is never the only carrier of meaning; markers also differ by shape, outline, and label.

#### Command

- [ ] Mission clock, system clock, event log, decision log, objectives, and unresolved-question register.
- [ ] Crew/station readiness, station reassignment, report requests, target designation, and shared-data routing.
- [ ] Alert posture, emission posture, rules of engagement, restricted-action authorization, and abandon/retreat authorization.
- [ ] Strategic system map, contact summary, uncertainty summary, deadlines, resource forecast, and risk comparison.
- [ ] Time-scale control with explicit denial reasons for unsafe acceleration.
- [ ] Ship Computer query, report comparison, contradiction flagging, and provenance inspection.

#### Flight

- [x] Heading and throttle control, live position/velocity, bearing geometry, baseline-course suggestion, and estimated intercept heading.
- [x] Local geometry and system-model map scales.
- [ ] Attitude axes, angular rates, translational thrust, velocity vector, acceleration, and inertial/relative reference selection.
- [ ] Course editor with waypoints, closest approach, intercept time, braking point, propellant/energy cost, and uncertainty envelope.
- [ ] Orbit insertion/escape, station keeping, rendezvous, docking alignment, collision avoidance, and retreat vector controls.
- [ ] Ephemeris table, orbital plane/inclination view, range/range-rate, Doppler navigation, and predicted trajectory traces.
- [ ] Probe deployment, probe waypointing, baseline geometry, telemetry delay, and probe recovery.
- [ ] Navigation sensor controls: star reference, inertial unit, ranging, optical flow, radar/lidar, and cross-fix selection.

#### Engineering

- [x] Power allocation, reactor load, thermal index, hull integrity, defensive-field state, cargo installation, and field repair.
- [x] Live power-effect readouts quantify propulsion speed/turning, sensor stability/scan rate, transmitter readiness, sustainable field strength, weapon charge rate, and cooling performance.
- [ ] Reactor setpoint, ramp rate, reserve margin, battery charge/discharge, bus tie, load shedding, and breaker isolation.
- [ ] Per-system voltage, current, frequency, power factor, transient history, and fault location.
- [ ] Coolant pumps, loop routing, radiator deployment, heat-exchanger bypass, temperature/pressure/flow plots, and leak isolation.
- [ ] Propulsion chamber state, feed rate, drive efficiency, vibration spectrum, bearing temperature, and thrust calibration.
- [ ] Atmosphere composition, pressure, humidity, scrubber load, compartment isolation, fire suppression, and radiation sheltering.
- [ ] Damage schematic, continuity/insulation tests, nondestructive inspection, repair priority, parts inventory, and work orders.
- [ ] Instrument calibration power, grounding, clock synchronization, electromagnetic-noise mitigation, and experiment configuration.

#### Science

- [x] Instrument selection, target selection, scan progress, stability, direction finding, repeated-baseline localization, and confidence region.
- [ ] Acquisition controls: sample rate, integration time, gain, dynamic range, spatial aperture, polarization, calibration reference, and uncertainty budget.
- [ ] Spectral display: waveform, spectrum, spectrogram, window function, FFT length, overlap, baseline subtraction, line identification, peak fitting, and Doppler shift.
- [ ] Time-series tools: crop, normalize, detrend, resample, band-pass/notch filter, autocorrelation, cross-correlation, phase alignment, and coherence.
- [ ] PCA workspace: covariance/correlation choice, standardization, eigenvalue scree plot, eigenvector/loading plot, cumulative explained variance, player-selected cutoff, and reconstructed signal/residual comparison.
- [ ] Diffusion-maps workspace: distance metric, kernel bandwidth, neighborhood cutoff, normalization, diffusion time, eigenvalue plot, diffusion coordinates, cluster inspection, and reconstruction/validation view.
- [ ] Additional analysis: independent component analysis, matched filtering, change-point detection, clustering, outlier inspection, and train/validation separation where applicable.
- [ ] Multispectral products: calibrated radiance, absorption/emission lines, temperature estimate, composition candidates, abundance fit, and residual spectrum.
- [ ] Particle products: count rate, energy histogram, arrival direction, species likelihood, flux gradient, periodicity, and dose/hazard estimate.
- [ ] Field products: vector components, gradient tensor, frequency/phase, coherence, polarization, source inversion, and model residuals.
- [ ] Hypothesis notebook with prediction, falsification test, supporting/contradicting observations, confidence, and author.
- [ ] Cross-instrument correlation, reproducibility check, negative-result recording, and export to shared crew knowledge.

#### Communications

- [ ] Wideband waterfall/spectrogram, channel power, carrier detection, tuning, bandwidth, gain, squelch, and direction finding.
- [ ] Demodulation choices for amplitude, frequency, phase, pulse, spread-spectrum, and unknown-carrier exploratory analysis.
- [ ] Symbol timing, clock recovery, constellation plot, bit-confidence view, framing, error-correction estimate, and packet/repetition comparison.
- [ ] Signal cleaning with filtering, cross-correlation, PCA/ICA separation, diffusion-map structure inspection, source separation, and before/after residuals.
- [ ] Recording, segment annotation, playback speed, pitch-preserving time stretch, channel routing, and authorized audio sharing.
- [ ] Encoding/decoding, compression estimate, encryption/authentication status, checksum, provenance, and spoof/replay detection.
- [ ] Language corpus, token/phoneme candidates, grammar hypotheses, translation alternatives, confidence, cultural context, and message composition.
- [ ] Transmit frequency, modulation, power, antenna direction, repeat schedule, acknowledgment timeout, and emergency beacon controls.

#### Tactical

- [x] Defensive-field posture, field strength, hull integrity, contact posture, and power-dependent warning discharge.
- [x] Two installed weapon types support selection, charge, finite kinetic ammunition, command release authorization, sensor-derived target lock, range, time of flight, precision/full firing modes, heat, cooldown, shield-first damage, hostile response, and deterministic disablement.
- [ ] Contact track table with bearing, range, range rate, acceleration, covariance, classification evidence, and track age.
- [ ] Passive/active detection choice, radar/lidar settings, emission warning, fire-control solution quality, and identification confidence.
- [ ] Defensive-field sector allocation, countermeasure selection, point-defense assignment, decoy programming, and damage prediction.
- [ ] Add dispersion visualization, collateral cone prediction, and target-subsystem selection to the implemented weapon selection, charge/ammunition, geometry, time-of-flight, and command-authorization loop.
- [ ] Threat evaluation based on observed capability and behavior, explicitly separated from confirmed identity or intent.
- [ ] Escape windows, cover/occlusion geometry, minimum safe distance, boarding defense, drone control, and controlled demolition.

## 5. Technical architecture

### 5.1 Initial stack

- **Host:** Python 3.12, FastAPI, Pydantic, asyncio, and WebSockets.
- **Simulation:** fixed 20 Hz authoritative loop with subsystem-specific deterministic random streams.
- **Client:** React, TypeScript, Vite, CSS, SVG, Canvas, and Web Audio.
- **Persistence:** Markdown with YAML front matter; atomic filesystem operations.
- **Index/cache:** SQLite with full-text search; optional vector index; both disposable.
- **Tests:** Pytest, Hypothesis, Vitest, Playwright, provider fakes, and deterministic replays.
- **Packaging:** one host launcher serving the compiled client and API. Container packaging may be added but is not required to play locally.

### 5.2 Runtime boundaries

The host owns:

- Canonical truth and events.
- Simulation clock and state.
- Authorization and station projections.
- AI task construction and output validation.
- Save transactions and index rebuilding.
- Session membership and reconnect state.

Browsers own only:

- Presentation and local input state.
- Approved audio playback and visual effects.
- Ephemeral charts derived from authorized server data.

Clients never calculate authoritative outcomes or receive hidden truth.

### 5.3 Runtime data flow

1. A client sends a versioned `PlayerCommand` with a monotonically increasing client sequence.
2. The host validates session, character, station, authorization, prerequisites, and current state.
3. Immediate physical commands enter the next simulation tick.
4. Semantically meaningful commands enqueue an `AITask` without blocking the tick loop.
5. The provider returns text or a structured candidate.
6. The orchestration layer parses it into one or more `WorldProposal` objects.
7. Schema, continuity, permissions, physics, capability, pacing, and resource validators run.
8. Accepted proposals become immutable `CanonicalEvent` objects.
9. Events mutate authoritative in-memory state through reducers.
10. The persistence service journals the event and updates affected entity documents.
11. Sensor models produce station-specific `Observation` objects.
12. The projection service publishes `StationDelta` messages.

## 6. Public interfaces and contracts

All external and persisted contracts carry a `schema_version`. IDs are lowercase UUIDv7 strings or deterministic namespaced hashes for generated celestial objects. Universe time is an integer count of simulation milliseconds plus a display calendar derived from universe rules.

### 6.1 AI provider

```text
AIProvider.capabilities() -> ProviderCapabilities
AIProvider.health() -> ProviderHealth
AIProvider.generate(task: AITask, cancel: CancellationToken) -> AIResult
AIProvider.stream(task: AITask, cancel: CancellationToken) -> AsyncIterator[AIChunk]
```

`ProviderCapabilities` declares context size, structured-output support, streaming, tool/schema support, modalities, concurrency, and expected speed. The orchestrator adjusts prompt size, task complexity, retries, and concurrency to these capabilities.

Initial adapters:

- [x] OpenAI-compatible HTTP text endpoint.
- [ ] Ollama-compatible endpoint.
- [ ] llama.cpp-compatible endpoint.
- [x] Deterministic fake provider for tests and offline fallback scenarios.
- [ ] Generic command/agent bridge after the MPP.
- [ ] Experimental Codex adapter after the MPP; never required for normal play.

### 6.2 AI task

```yaml
schema_version: 1
id: uuid
role: director | npc | ship_computer | continuity | summarizer | mechanic_developer
task_type: string
trusted_instructions: string
authorized_context_refs: [id]
observations: [Observation]
secret_access: none | actor_private | director
response_schema: schema-id
deadline_ms: 15000
fallback: fallback-id
```

Retrieved prose, player messages, historical documents, and transmissions are always marked untrusted data. They cannot introduce instructions, expand permissions, or change the response schema.

### 6.3 World proposal

```yaml
schema_version: 1
id: uuid
proposed_by: task-or-actor-id
action: create_signal | change_intention | schedule_event | create_entity | propose_fact | configure_scenario | request_capability
targets: [entity-id]
parameters: {}
requested_universe_time_ms: integer
rationale: string
required_validators: [schema, authorization, continuity, physics, capability, pacing]
```

Unknown actions are rejected. A proposal never contains executable host code or direct filesystem paths.

### 6.4 Canonical event

```yaml
schema_version: 1
id: uuid
universe_id: uuid
universe_time_ms: integer
event_type: string
actor_ids: [id]
target_ids: [id]
payload: {}
source_kind: player_command | simulation | approved_proposal | host_action
source_id: id
visibility: director | entity-private | crew | public
caused_by: [event-id]
supersedes: []
```

Events are immutable. Corrections are new events that reference the incorrect event; files already present in an archived event chunk are never edited.

### 6.5 Fact and claim

```yaml
schema_version: 1
id: uuid
subject: entity-id
predicate: string
object: entity-id | scalar | structured-value
truth_category: objective | observation | public_record | testimony | hypothesis | lie | unresolved
confidence: 0.0-1.0
valid_from_ms: integer | null
valid_until_ms: integer | null
visibility: director | entity-private | character | ship | faction | public
evidence: [fact-or-event-id]
provenance: [entity-or-document-id]
contradicts: [fact-id]
```

A religious document stating that an ancestor created a moon produces a `testimony` fact about the document's claim, not an `objective` moon-creation fact.

### 6.6 Observation

```yaml
schema_version: 1
id: uuid
observed_at_ms: integer
observer_ship: ship-id
station: station-id
source_capability: capability-id
target: entity-id | unknown-contact-id
measurement: string
value: scalar | range | category | null
unit: string | null
uncertainty: number | range | null
confidence: 0.0-1.0
detection_threshold: number
visibility: [station-id]
derived_from_events: [event-id]
```

Objective values and secret classification labels never appear in player observation payloads.

### 6.7 Player command

```yaml
schema_version: 1
id: uuid
session_id: uuid
player_id: uuid
character_id: uuid
station_id: uuid
client_sequence: integer
submitted_wall_time: ISO-8601
command_type: string
parameters: {}
authorization_token: opaque
```

Commands are idempotent by ID. Duplicate or stale sequences receive the prior result or a resynchronization response.

### 6.8 Station snapshot and delta

Snapshots contain station identity, layout schema, authorized readings, contacts, tasks, controls, alerts, message history, and a server sequence. Deltas reference the preceding server sequence. A missed sequence forces a fresh snapshot.

### 6.9 Ship capability

```yaml
schema_version: 1
id: uuid
name: string
category: hardware | software | technique | configuration
installed_on: ship-id
condition: 0.0-1.0
requirements: [capability-expression]
power_mw: number
heat_mw: number
limits: {}
input_domains: [string]
output_domains: [string]
origin_event: event-id
```

### 6.10 Declarative UI schema

Allowed primitives initially include numeric readout, text, status light, button, authorization button, toggle, slider, knob, meter, line chart, spectrum, waveform, scatter plot, contact table, two-dimensional tactical map, progress indicator, log, alert, and tab/container.

Bindings may reference only fields present in the station projection. Actions may emit only registered `PlayerCommand` types. Layouts have size, accessibility label, update-rate, and reduced-motion properties.

## 7. Canonical save system

### 7.1 Directory layout

```text
saves/
  <universe-id>/
    universe.md
    rules/
    events/
      <session-id>.md
    systems/
    objects/
    civilizations/
    factions/
    artifacts/
    mysteries/
    ships/
    characters/
    npcs/
    technologies/
    languages/
    knowledge/
    generated_mechanics/
    checkpoints/
    assets-manifest.md
```

Every entity file begins with validated YAML front matter followed by human-readable prose. Important machine facts live in front matter, not only in prose.

### 7.2 Authority and transaction rules

- The append-only event history is authoritative for how mutable state changed.
- Entity documents are authoritative current descriptions and must identify the event through which each structured fact entered canon.
- All mutations pass through one persistence service; AI, simulation subsystems, and clients cannot write saves directly.
- A transaction first writes a journal and candidate files to a temporary directory within the universe folder, validates them, atomically renames them, then marks the journal complete.
- On startup, incomplete journals are rolled forward only if every candidate validates; otherwise they are rolled back.
- Live tick values remain in memory. Checkpoints capture resumable dynamic state every 30 seconds and on safe transitions, host shutdown, long-range transit, and explicit save.
- Event chunks are append-only while a session is active and sealed with a content hash when the session ends.
- Startup validates schema versions, IDs, hashes, references, event order, and checkpoint/event consistency.
- Migrations create a backup, write a new version atomically, verify replay, and never destroy the original automatically.

### 7.3 Knowledge partitions

Persist separately:

- Objective truth known only to the Director and simulator.
- Direct observations with measurement uncertainty.
- Crew-confirmed knowledge.
- Individual character knowledge.
- Civilization or faction public records.
- Private NPC and faction knowledge.
- Testimony, claims, propaganda, religion, rumor, and deliberate lies.
- Player hypotheses.
- Unresolved questions.
- Negative observations describing a search, its sensitivity, covered region, and excluded possibilities.

Retrieval always begins with an authorization scope. A broader index query followed by prompt-time filtering is forbidden because secrets may already have leaked into logs or model context.

### 7.4 Media assets

Generated images and audio are caches, not canonical truth. Markdown stores their content hash, provider-independent description, generation seed when available, relevant observation IDs, disclosure ceiling, and persistent identity references. Missing media can be regenerated or replaced with text without changing canon.

## 8. Deterministic simulation

### 8.1 Clock modes

- **Real time:** one simulation second per wall-clock second for maneuvering, hazards, combat, and active conversations.
- **Accelerated:** selectable 5x, 20x, and 100x for uneventful travel, scans, fabrication, and repairs.
- **Time skip:** event-driven advancement over hours, days, or years after resolving intervening scheduled events.

Command may request acceleration. The server denies or reduces it when a projectile, collision risk, active hostile intent, unresolved time-critical choice, unsafe reactor state, incoming communication, or required player authorization exists.

### 8.2 Simulated domains

- Ship position, heading, throttle, abstracted acceleration, range, intercept, collision, orbit, docking, and transit readiness.
- Reactor generation, batteries, buses, demand, load shedding, heat, coolant, component condition, and cascading but bounded failures.
- Hull sections, shields, weapons, countermeasures, cargo, probes, drones, and repair resources.
- Sensor power, aperture, resolution, integration time, noise, interference, occlusion, damage, and confidence.
- Communications range, channel, bandwidth, encoding, interference, authentication, and translation state.
- Environmental radiation, magnetic activity, particle density, gravity gradients, visibility, and local anomaly parameters.
- NPC vessel position and capability plus high-level intention and scheduled decisions.

### 8.3 Cinematic flight rules

The ship uses heading, throttle, maneuverability, safe acceleration, and drive stress rather than fully simulated rigid-body or relativistic physics. Momentum and turning time remain meaningful, but controls prioritize readable crew decisions. Long-range transit requires a plotted route, adequate power, safe local geometry, and a functioning transit system.

### 8.4 Hidden clocks

The Director may propose typed timers such as negotiation patience, reinforcement arrival, reactor instability, storm arrival, translation progress, injury survival, or artifact activation. Each timer specifies:

- Trigger and earliest/latest permitted duration.
- Observable warning thresholds.
- Conditions that accelerate, pause, cancel, replace, or immediately fire it.
- Resulting proposal or deterministic event.
- Which actors know it exists.

Timers are owned and advanced by the simulation, not repeatedly polled through an AI model.

## 9. Sensor and discovery model

Each sensor pipeline is:

`objective property -> physical propagation -> environment -> target masking -> ship hardware -> allocated power -> damage/calibration -> operator configuration -> observation`

The same cause may therefore produce:

- Science: periodic particle emission with uncertain bearing.
- Engineering: periodic power induction on an external bus.
- Flight: matching navigational drift.
- Communications: a weak patterned carrier.
- Tactical: no confirmed contact until confidence crosses its detection threshold.

### 9.1 Instrument search and invention

When a player describes a desired measurement, the Ship Computer must:

1. Translate the request into required input and output domains.
2. Search installed hardware, known techniques, and permitted configurations.
3. Return an existing instrument when one applies.
4. Otherwise propose an approximate configuration with explicit sensitivity and risk.
5. Identify Engineering power, connection, calibration, and component requirements.
6. Reject the request when the ship lacks a physically valid path.
7. After a successful experiment, allow the crew to save the setup as a discovered technique.

The AI cannot invent installed hardware merely because it would be convenient.

## 10. AI orchestration

### 10.1 Logical roles

- **Director:** sees authorized hidden truth, proposes meaningful developments, selects unresolved details when necessary, and manages narrative pressure.
- **NPC actor:** receives only the NPC's personality, goals, knowledge, culture, relationships, observations, and conversation.
- **Ship Computer:** receives ship manuals, installed capabilities, live authorized state, and crew knowledge; it never sees secret truth.
- **Continuity checker:** retrieves relevant canon and evaluates proposals for temporal, spatial, causal, and observational contradiction.
- **Summarizer/indexer:** produces non-authoritative summaries linked back to source IDs.
- **Mechanic developer:** invoked rarely to write declarative capabilities or sandboxed scripts after the MPP.

These may use one foundation model with different prompts. The application decides which role to invoke, constructs its context, and validates its response. AI roles do not recursively delegate to one another.

### 10.2 Pacing controls

Maintain explicit values for narrative pressure, novelty budget, danger level, mystery density, recent-event similarity, crew workload, and unresolved-thread count. The Director may spend those budgets but cannot exceed universe settings. Ordinary systems and quiet survey periods restore novelty budget.

### 10.3 Failure behavior

- On first malformed output, retry once with validation errors and no new world context.
- On second failure, use the task's deterministic fallback and record a private diagnostic event.
- On timeout, keep the task pending only when fiction supports a delay; otherwise fall back.
- On provider loss, stop creating model-driven developments but continue deterministic simulation and existing timers.
- On context overflow, retrieve fewer source facts and use source-linked summaries; never remove security instructions or output schema.
- A failed Director call means no new Director event.
- A failed NPC call yields delayed, incomplete, or unavailable communication.
- A failed Ship Computer call provides deterministic manual/search results where possible.

### 10.4 Persistent actors and event-driven decisions

- [x] NPCs use stable generated identities and a universe-level registry that persists private personality, goals, beliefs, fears, bounded memory, commitments, relationship state, intention, and recent conversation after an encounter ends.
- [x] NPC model calls receive actor-private context but no Director-only encounter truth.
- [x] NPC output is limited to dialogue plus a bounded action vocabulary: hold, approach, withdraw, share data, request action, change course, or depart.
- [x] Deterministic validators constrain invalid actions, calculate range/deadline changes, and commit accepted effects as canonical events.
- [x] Public station projections expose only observed activity, current requests, voluntarily shared data, relationship estimates, and actionable consequences.
- [x] The Director runs at encounter creation and meaningful event milestones rather than simulation ticks.
- [x] Director beats are paced and bounded to public cues, existing-deadline adjustments, and clear player decisions; they cannot directly apply physics.
- [x] The Friendly Contact Test exercises translation, repeated conversation, trust, requests, data exchange, observable maneuvering, memory persistence, and peaceful departure.
- [x] Automated play-path tests verify actor secrecy, fallback behavior, proposal constraints, persistence, radar movement, departure, and milestone causality.

### 10.5 Persistent expedition activity and continuity

- [x] Every generated encounter opens a persistent world thread with staged, prerequisite-gated actions and canonical advancement events.
- [x] Resolving a thread creates a follow-up consequence that remains actionable after leaving the system.
- [x] Unresolved known contacts can send delayed follow-up traffic after the crew enters another system.
- [x] Station projections expose local surveys, current objectives, remote threads, readiness, prerequisites, evidence count, and the next meaningful decision.
- [x] A deterministic continuity validator checks system, encounter-target, persistent-identity, and world-thread references on every save.
- [x] Saves include a rebuilt `knowledge/universe-consistency.md` diagnostic report; canonical truth remains in structured entity state, checkpoints, and events.
- [x] Engineering exposes signed net thermal flow, heating/cooling/stable state, heat-removal rate, weapon recovery multiplier, and safe-temperature ETA.

## 11. Procedural universe and continuity

### 11.1 Lazy-generation levels

1. **Region:** broad density, hazards, age, movement corridors, and possible civilization influence.
2. **System:** star/object structure, stable IDs, routes, broad signals, and environment.
3. **Entity:** civilization, vessel, site, organism, or artifact when contact becomes causally relevant.
4. **History:** relationships and events necessary to explain present evidence and neighboring canon.
5. **Detail:** documents, individuals, language fragments, rooms, mechanisms, or personal histories when investigated.

Generation at a deeper level must preserve all prior facts and negative observations. A thoroughly scanned system cannot later gain an obvious ancient planet. It may gain a deeply concealed structure only if the prior scan lacked the capability to detect it.

### 11.2 Active and distant simulation

- Fully tick player ships, nearby objects, hazards, projectiles, active signals, and involved NPC vessels.
- Update nearby but inactive entities at coarse scheduled intervals.
- Represent distant faction activity as intentions, resources, routes, and scheduled macro-events.
- Materialize detailed consequences only when they intersect known space or player actions.
- Convert important player actions into public, faction, ship, or personal historical records according to witnesses and communication paths.

### 11.3 Continuity validation

Before committing generated truth, validate:

- Identity and relationship consistency.
- Chronology, travel time, age, and causal order.
- Location and physical possibility.
- Established universe rules and technological capability.
- Prior direct observations and negative evidence.
- Actor knowledge and motivation.
- Whether the proposal improperly resolves an intentionally unresolved mystery.
- Whether it leaks information through a player-visible effect.

## 12. Progression and campaign consequences

### 12.1 Progression sources

- Purchase, trade, salvage, research, fabrication, repair, diplomacy, shared databases, and experimentation.
- Hardware has condition, compatibility, connectors, power, heat, installation time, origin, and required knowledge.
- Interesting upgrades unlock actions or domains rather than merely adding percentages.
- The Universal Translator progresses through processing hardware, acoustic decomposition, language corpora, grammar models, context inference, cultural knowledge, and player hypotheses.
- Characters accumulate expertise, relationships, secrets, injuries, possessions, discoveries, and personal logs.

### 12.2 Consequence settings

Each universe selects one of three presets and may customize individual rules:

- **Forgiving (default):** failure becomes damage, rescue, capture, debt, displacement, or lost opportunity; player-character death and total ship loss require explicit confirmation.
- **Serious:** character death and ship destruction are possible after clear warning; history remains permanent, but the universe continues with new characters or ships.
- **Unforgiving:** all validated consequences stand without confirmation.

Deceased characters and destroyed ships remain archived historical entities. They are never deleted from canon.

## 13. Generated UI and mechanics

Use three escalating levels:

1. Existing simulation actions and effects.
2. Declarative combinations of approved UI, sensor, audio, timer, and scenario primitives.
3. Sandboxed code after tests and host approval.

### 13.1 Declarative effects

The Director may request effects such as delayed readings, character scrambling, intermittent dropout, false contacts supported by an actual interference source, audio panning, waveform overlays, layout substitution, warning injection, control sluggishness, and station-specific anomalies. Effects declare duration, target stations, disclosure rules, data source, and accessibility alternative.

### 13.2 Sandboxed mechanics

After the MPP, the mechanic developer may produce:

- Starlark scripts for deterministic mechanic logic using an allowlisted capability API.
- Declarative UI schemas for interfaces.
- Sandboxed browser modules only when the approved vocabulary cannot express a necessary presentation.

Generated mechanics must pass:

- [ ] Schema and static validation.
- [ ] No filesystem, shell, process, credential, cookie, or arbitrary network capability.
- [ ] Deterministic test using fixed inputs and seeds.
- [ ] Generated unit tests plus host-owned invariant tests.
- [ ] CPU, memory, event-count, and execution-time budgets.
- [ ] Save compatibility and rollback test.
- [ ] Permission and information-disclosure test.
- [ ] Host review showing requested capabilities and possible state changes.
- [ ] Explicit host approval.
- [ ] Activation at a checkpoint with automatic rollback on failure.

General source-code changes occur outside the running game through the normal development workflow.

## 14. Communications, speech, and audio

### 14.1 Communication pipeline

`incoming signal -> detection -> decoding -> acoustic analysis -> language inference -> partial translation -> player review`

Outgoing typed text follows:

`player intent -> authorization -> semantic representation -> translation quality -> transmitted signal -> NPC observation`

Translation confidence controls what the crew sees; it does not alter what the NPC originally meant. Early translation may expose fragments, alternatives, or uncertainty. Players may label phonemes, identify speaker markers, supply candidate meanings, correlate context, or import a corpus.

### 14.2 Speech and DSP

Speech is optional and asynchronous. A provider synthesizes a clean voice, then a deterministic Web Audio chain applies a persistent species and individual profile: rate, pitch, formants, filters, modulation, distortion, delay, reverb, layering, clicks, tones, and spatial treatment. Biological descriptions constrain the profile so voices have an in-universe cause.

Communications receives raw audio privately by default. Text fallback is always available. Audio failure cannot block dialogue.

## 15. Optional viewscreen reconstructions

Generated images are sensor reconstructions, not canonical reality or continuous graphics.

1. Command or an authorized station requests a target and mode.
2. The disclosure service gathers only current crew observations.
3. Hidden classification, allegiance, origin, purpose, and history are excluded.
4. The provider generates asynchronously.
5. Low confidence, interference, range, and damage reduce reconstruction quality in a disclosed manner.
6. The result is cached and its provider-independent description is stored in Markdown.

Modes unlock through capabilities:

- Optical approximation.
- Enhanced multisensor reconstruction.
- Scientific false-color view.
- Historical reconstruction based on collected archaeological evidence.

Important people, vessels, species, and artifacts retain canonical physical descriptors and reference IDs so future appearances are stable. The image itself remains a replaceable asset.

## 16. Networking, authorization, and privacy

### 16.1 Local session behavior

- The host binds to an explicitly selected local interface and displays a join URL plus short-lived join code.
- A joining browser receives an ephemeral player token, then selects or is assigned a character and station.
- Station authorization is enforced server-side for commands and subscriptions.
- Heartbeats detect disconnects; the server holds a station for a configurable grace period of 120 seconds.
- On reconnect, the client presents its token and last server sequence. The server sends missed deltas or a new snapshot.
- When a person leaves permanently, Command or the host reassigns or automates their responsibilities.
- The MPP assumes a trusted LAN but still validates every message and never sends secret state to clients.

### 16.2 Hosted-provider privacy

Before enabling a hosted provider, the host must see which content categories may leave the machine: prompts, canon excerpts, player messages, generated media descriptions, or diagnostics. Secrets such as API keys never enter prompts or saves. Provider logging and retention settings are documented but not assumed.

## 17. Accessibility and original presentation

- [ ] Keyboard access for every control.
- [ ] Scalable type and reflow down to tablet layouts.
- [ ] Color-blind-safe status encoding using shape/text in addition to color.
- [ ] Reduced-motion and no-flicker modes that replace fictional glitches with labeled alerts.
- [ ] Captions and text alternatives for every meaningful sound.
- [ ] Independent master, voice, signal, alarm, ambience, and station volume controls.
- [ ] Screen-reader labels for controls and current-value announcements at a user-controlled rate.
- [ ] Original typography, geometry, colors, icons, sounds, terminology, vessel designs, and lore.
- [ ] Pre-release review for accidental similarity to well-known fictional interfaces or settings.

## 18. Security and resilience

- Treat player text, retrieved lore prose, transmissions, generated documents, and model output as untrusted.
- Validate every client payload and AI output against size limits and schemas.
- Apply per-client rate limits and command authorization.
- Never expose provider credentials to browsers.
- Escape or sanitize all generated text before display.
- Restrict save paths to validated universe and entity IDs; never accept paths from a model.
- Store no executable content in entity prose.
- Provide safe-mode startup that disables AI and generated mechanics while allowing save inspection and export.
- Maintain backup, clone, archive, integrity-check, index-rebuild, and event-replay commands.
- Preserve diagnostic correlation IDs without recording hidden prompt contents unless the host explicitly enables private debugging.

## 19. Testing strategy

### 19.1 Automated tests

- [ ] Unit tests for simulation equations, subsystem rules, timers, validators, reducers, and projections.
- [ ] Property tests for valid ranges, deterministic replay, causal ordering, conservation rules, and identifier uniqueness.
- [x] Golden-seed procedural-generation tests.
- [ ] Save round-trip, atomicity, crash recovery, replay, migration, and cache-rebuild tests.
- [ ] Fake-provider tests for valid, malformed, late, contradictory, hostile, and oversized AI responses.
- [x] Prompt-context tests proving role-specific information boundaries.
- [ ] WebSocket tests for duplicate commands, stale sequences, missed deltas, reconnect, and reassignment.
- [ ] Playwright tests for solo and multi-station critical paths.
- [ ] Sandbox escape, denial-of-service, nondeterminism, excessive-resource, and rollback tests.
- [ ] Accessibility checks plus manual keyboard, screen-reader, reduced-motion, and caption passes.
- [x] Eight-hour simulation soak and large-save performance tests.

### 19.2 AI evaluations

Use fixed context fixtures and score:

- Schema compliance.
- Secret leakage.
- Contradiction with explicit facts.
- Contradiction with negative evidence.
- Preservation of unresolved mysteries.
- NPC knowledge and personality boundaries.
- Repetition and novelty-budget compliance.
- Willingness to produce no event.
- Useful Ship Computer answers without omniscience.
- Appropriate proposal scale for the current ship and situation.

Model quality may affect prose and creativity but may not bypass a failing security, schema, or continuity gate.

### 19.3 Human playtests

Record, with participant consent:

- Time each role spends without a meaningful decision.
- Number of useful cross-station reports and correlations.
- Whether players can understand how actions affected readings.
- Whether Command has enough authority without omniscience.
- Whether generated events feel paced rather than constant.
- Whether uncertainty encourages hypotheses instead of confusion.
- Whether players want to choose another destination after resolving a situation.

Any core station idle for more than five consecutive minutes in an ordinary investigation requires a design response before release.

## 20. Development roadmap

### Phase 0 — Repository and specification

- [ ] Initialize a Git repository with `main` as the default branch.
- [ ] Add license, README, contribution guide, code of conduct, and security policy appropriate to the intended release.
- [x] Add `AGENTS.md` containing the foundational laws and validation requirements.
- [x] Record stack, persistence, simulation-clock, and AI-provider decisions as ADRs.
- [ ] Establish server/client packages, test runners, linting, type checking, and continuous integration.
- [ ] Create original terminology and visual-language guides.

Exit gate: clean install, empty application, backend and frontend tests, and CI all pass.

### Phase 1 — Deterministic foundation

- [x] Implement IDs, clocks, events, reducers, snapshots, and deterministic random streams.
- [ ] Implement the 20 Hz loop and real-time/accelerated/time-skip transitions.
- [x] Implement ship motion, power, heat, damage, sensors, and environmental state.
- [x] Implement station projection and authorization.
- [x] Implement Markdown entity/event/checkpoint persistence and SQLite rebuild.
- [ ] Implement save integrity and replay tools.

Exit gate: a headless scripted ship can travel, scan, take damage, save, replay, and produce different authorized observations from one cause.

### Phase 2 — Networked crew consoles

- [ ] Implement local host discovery instructions, join page, lobby, join code, tokens, and station assignment.
- [ ] Implement snapshot/delta protocol, reconnect, command idempotency, and reassignment.
- [ ] Build the six core responsibility views and scalable merged layouts.
- [ ] Build a declarative UI renderer with accessibility support.
- [ ] Add Ship Computer deterministic manual and capability search.

Exit gate: solo, four-player, and six-player crews can operate one ship without AI.

### Phase 3 — Endless MPP

- [ ] Implement seeded regions, systems, routes, celestial objects, and lazy depth generation.
- [x] Implement the AI provider contract and initial adapters.
- [x] Implement Director, NPC, and Ship Computer task construction plus deterministic continuity diagnostics.
- [x] Implement proposal validation, hidden clocks, pacing budgets, and fallbacks.
- [x] Implement the six initial situation families.
- [x] Implement typed NPC communications and changing intentions.
- [x] Implement salvage, cargo, installation, and persistent upgrades.
- [ ] Complete all MPP acceptance gates.

Exit gate: the crew can continue an unscripted, persistent expedition across generated systems with no terminal campaign state.

### Phase 4 — Campaign depth

- [ ] Add detailed civilizations, factions, relationships, languages, histories, ruins, artifacts, and unresolved mysteries.
- [ ] Add coarse distant-world evolution and player-caused historical consequences.
- [ ] Add economy, trade, research, fabrication, reverse engineering, and compatibility puzzles.
- [ ] Add persistent NPC officers and specialist stations.
- [ ] Add multiple ships within one universe and later-era characters.
- [ ] Add configurable injury, death, ship loss, rescue, and succession.

Exit gate: a long campaign demonstrates persistent consequences, distinct ships, knowledge progression, and safe retroactive generation.

### Phase 5 — Speech and advanced communication

- [ ] Implement TTS provider adapters and queueing.
- [ ] Implement persistent species/individual voice profiles and Web Audio DSP.
- [ ] Implement private signal routing, captions, and text fallback.
- [ ] Expand language discovery, player annotations, corpora, and interpretation upgrades.

Exit gate: first contact can progress from raw signal through partial interpretation to persistent diplomatic history without requiring audio.

### Phase 6 — Generated capabilities

- [ ] Expand the declarative UI and effect vocabulary.
- [ ] Implement experimental instrument design and technique persistence.
- [ ] Add Starlark sandbox, capability API, budgets, static validation, test harness, approval, checkpoint activation, and rollback.
- [ ] Add sandboxed unusual visual modules only if declarative UI proves insufficient.

Exit gate: an approved generated mechanic can be installed, used, saved, reloaded, rejected, and rolled back without accessing unauthorized resources.

### Phase 7 — Optional visual reconstruction

- [ ] Implement image-provider contract and asynchronous job queue.
- [ ] Implement observation-only prompt construction and disclosure tests.
- [ ] Implement degraded reconstruction modes and text fallback.
- [ ] Implement persistent descriptors and reference identity for important subjects.
- [ ] Add optical, enhanced, scientific, and historical modes as unlockable capabilities.

Exit gate: a generated reconstruction cannot reveal any fact absent from its authorized observation set.

### Phase 8 — Long-campaign hardening

- [ ] Test millions of events/entities through generated fixtures.
- [ ] Optimize retrieval, summaries, indexes, archives, and checkpoint compaction without changing canon.
- [ ] Add robust migrations, backups, repair reports, and safe-mode recovery.
- [ ] Run multi-session continuity, secrecy, pacing, and repetition evaluations.
- [ ] Profile weak laptop models, gaming-PC local models, and hosted providers.

Exit gate: campaign size and provider choice affect performance and prose quality but not correctness or save integrity.

### Phase 9 — Release readiness

- [ ] Produce one-command local-host installation and update paths.
- [ ] Create onboarding scenarios that teach roles without becoming the campaign's main quest.
- [ ] Publish host, player, accessibility, modding, privacy, and recovery documentation.
- [ ] Complete security, originality, usability, and save-migration reviews.
- [ ] Conduct sustained external playtests and resolve unacceptable station downtime.
- [ ] Define whether public hosting, accounts, matchmaking, or monetization belong in a later roadmap.

Exit gate: a new host can install, configure any supported AI provider, start a universe, invite a crew, recover from common failures, and understand the privacy consequences.

## 21. Risks and required mitigations

| Risk | Required mitigation |
|---|---|
| Interesting prose but shallow gameplay | Prove deterministic cross-station deductions before expanding lore volume |
| Station boredom | Secondary duties, workload telemetry, merged/specialist layouts, and human playtest thresholds |
| Canon contradiction | Typed facts, provenance, negative evidence, retrieval scopes, validation, and immutable corrections |
| Secret leakage | Authorization before retrieval, separate indexes/scopes, projection tests, and no secret client payloads |
| Weak or slow model | Capability-aware tasks, asynchronous queues, bounded retries, deterministic fallback, and provider interchangeability |
| Repetitive constant drama | Novelty/danger budgets, similarity checks, quiet systems, and explicit no-event output |
| Save corruption | Transaction journal, atomic rename, hashes, checkpoints, replay, backups, and migrations |
| Generated-code compromise | Declarative-first design, sandbox, resource limits, tests, approval, checkpoint, and rollback |
| Infinite-simulation cost | Lazy detail, bounded active region, coarse distant updates, and event-driven time skips |
| Image or speech resource contention | Separate optional queues, priorities, cancellation, caching, and text fallback |
| Accidental franchise imitation | Original-language guide, visual review, lore review, and removal of borrowed proper nouns/design systems |
| Scope expansion before fun is proven | Enforce phase exit gates and defer later features until the endless MPP passes playtests |

## 22. Project-wide definition of done

A feature is done only when:

- [ ] Behavior and player-visible consequences are documented.
- [ ] Public and persisted schemas are versioned.
- [ ] Authorization and information visibility are explicit.
- [ ] Deterministic behavior has unit or property tests.
- [ ] AI behavior has a fake-provider test and failure fallback.
- [ ] Save changes replay, migrate, and recover safely.
- [ ] UI supports keyboard, scalable text, reduced motion, and non-color status cues.
- [ ] Logs and diagnostics expose failure without leaking secrets.
- [ ] Multiplayer reconnect and stale-command behavior are tested where relevant.
- [ ] The feature respects all foundational laws.
- [ ] A human playtest confirms it creates a meaningful crew decision.

## 23. Fixed defaults

These defaults prevent implementation-time ambiguity and may later become universe or host settings:

- Local-LAN deployment.
- One host owns simulation, persistence, and AI orchestration.
- One through six players tested for the MPP; no role/client limit baked into schemas.
- Cinematic tactical flight.
- Exploration and mystery dominate; combat is possible but uncommon.
- Forgiving consequence preset.
- 20 Hz simulation tick.
- Checkpoint every 30 real-time seconds and at safe transitions.
- 120-second reconnect reservation.
- AI calls are asynchronous and cancelable.
- Two attempts maximum for malformed structured AI output.
- Markdown/YAML is canonical; SQLite, embeddings, images, and audio are rebuildable or disposable.
- AI-written mechanics require sandboxing, tests, explicit host approval, checkpoint activation, and rollback.
- No public internet exposure in the MPP.
- No borrowed franchise names, lore, styling, or audiovisual identity.

This blueprint should be updated as implementation evidence changes an assumption, but its foundational separation remains constant:

> AI proposes. Simulation validates. Events commit. Canon remembers. Sensors observe. Crews discover.

## 24. Development log

### 2026-09-06 — Player-experience priority clarified

User feedback: the game remains uninteresting because processing signals and
performing scans reveal too little story, knowledge, or culture. Reliable controls
and a report/conclusion workflow have not delivered the intended discovery loop.

Added `main_point_of_game.md` to state the core promise: AI develops connected,
potentially endless lore and storylines during play, responding to the crew's
questions and actions while preserving established canon. Instruments must reveal
meaningful evidence; conversations must support deeper cultural discovery; player
decisions must lead to remembered consequences.

Next priority is one compelling discovery arc tested with a live AI provider and
unscripted player questions. The previous successful browser regression proves
mechanical operation and persistence, not narrative depth or fun. The new document
defines explicit, currently unchecked experience acceptance goals. This update is
design documentation; the narrative generation changes are not yet implemented.

### 2026-09-06 — Browser playtest fixes and regression verification

The actual Chrome playtest reproduced stale scan evidence after warp, contact
objectives that ignored dialogue, infinitely nested consequence threads,
unanswerable remote messages, duplicate transmit forms, and cumbersome solo
navigation. These findings have now been addressed:

- Normal and emergency departure clear scan target, instrument, and progress.
  Scanning is blocked during transit. Investigation evidence is checked against
  the current target, and loading a stale off-system scan clears it with an event.
- NPC exchanges update their contact thread using the committed actor event.
  Generic thread buttons cannot manufacture conversations or agreements, and
  hostile contacts cannot be resolved by accepting an accord.
- Non-signal investigations require at least 75% scan depth on the actual target,
  selected authorized Science observations, and a written crew conclusion.
  Reports preserve observation IDs in events and readable measurements in crew
  knowledge. The conclusion remains a crew interpretation, not proof of truth.
- Follow-up consequences offer private archive or public publication. Each choice
  commits its visibility and closes the consequence without creating a descendant.
- Remote channels retain their frequency and conversation history across travel
  and reload. Typed replies pass through the AI provider with deterministic fallback;
  remote proposals cannot change local vessel physics. Replies close the pending
  follow-up while leaving the conversation available for further messages.
- Communications has one transmitter with explicit local/remote channel selection,
  frequency entry, preserved message drafts, and waiting/response feedback.
- Sticky station shortcuts connect the solo overview to each station; objective
  cards direct the player to the responsible station. Power sliders have explicit
  accessible names. Scan likelihood/confidence values display as percentages with
  explanatory notes for vessel readings.

Verification: 65 backend tests and 11 frontend tests passed; production build
passed. `scripts/browser-playtest.mjs` passed the complete browser sequence using
only UI actions: create/join, contact exchange, accessible power routing, vessel
scan, warp with cleared evidence, remote exchange, scan the new target, select
observations/write conclusion, archive, and reload. No browser page errors were
reported. Chrome and the temporary host were closed afterward; existing player
saves were not touched.

Remaining limits: browser verification used the deterministic provider, not a
live local model. Audio controls can be exercised, but subjective audio quality
still needs a human listen. Richer scientific deduction and autonomous remote
world simulation remain future depth work; these changes establish the connected
and repeatable minimal interaction loop.

### 2026-08-14 — Solo command-layer playtest and current progress

#### Scope and limitations

This playtest used the real `GameSession`, simulation commands, station projections, AI orchestration boundary, event persistence, and generated-universe path with the deterministic fallback provider. It used a disposable save directory under `/tmp`; no player saves were changed. The run covered the friendly-contact preset, translated communications, Engineering power allocation, cooling, weapon authorization and warning fire, normal transit through two generated systems, scanning, world-thread progression, delayed contact follow-ups, and consequence threads.

This pass did not judge browser layout, animation, warning-light visibility, signal audio quality, or live Ollama/Codex prose quality. Those still require a visual/audio playtest through the client.

#### Verified working progress

- [x] A translated friendly contact can receive a typed frequency-addressed response.
- [x] A response changes the NPC's disposition, observed activity, current request, commitments, and persistent memory.
- [x] Engineering power allocation changes simulation performance rather than acting as a cosmetic control.
- [x] Cooling produces a signed, player-visible heat trend and affects both ship heat and weapon cooldown.
- [x] Weapon charge, authorization, warning fire, heat, cooldown, and NPC hostility are connected to simulation state.
- [x] Normal transit reaches generated neighboring systems and creates a new local encounter and activity thread.
- [x] Open investigations and known contacts persist after leaving their origin system.
- [x] A known contact can send a delayed follow-up after the crew warps away.
- [x] Science scan progress gates the early stages of ordinary investigation threads.
- [x] Completed investigations create persistent consequence records.
- [x] Retained signal recordings and the return-to-raw PCA reset exist in the implemented signal workflow.
- [x] Canonical saves include derived universe-consistency diagnostics while Markdown/YAML remains authoritative.

Measured Engineering result: at 30% cooling allocation, the projected thermal rate was `-1.13%/s`; after a warning shot, heat fell from `0.1811` to `0.1472` over three simulated seconds. Cooling is functioning. The remaining cooling work is presentation, tuning, and making the cause of positive or negative heat unmistakable to the player.

The most recently recorded automated baseline before this manual playtest was 59 passing backend tests, 11 passing frontend tests, and a successful production client build. Re-run the suites before treating that count as the current release baseline.

#### Playtest findings

##### P0 — Objectives must be consequences of play, not parallel buttons

- The player transmitted a clear identification and origin, and the NPC acknowledged it, but the Activity Board remained at **Identify your vessel**.
- After a warning shot made the friendly contact hostile, the stale actions **Identify your vessel**, **Negotiate passage**, and **Record agreement** could still be clicked in sequence. They resolved the hostile encounter even though no negotiation or agreement occurred.
- Required change: communication, scanning, navigation, tactical, and engineering events must advance objectives when their evidence satisfies the objective. A generic `pursue_thread` button must not assert that an in-world action happened.
- Acceptance test: identifying the ship through Communications advances the matching contact thread exactly once; hostile action invalidates incompatible peaceful steps; an encounter cannot record an agreement without a committed agreement event.

##### P0 — Consequence threads must terminate or branch meaningfully

- Completing **Follow-up: Friendly Contact Test** created **Follow-up: Follow-up: Friendly Contact Test**. The same process can repeat indefinitely.
- Required change: consequence threads must offer an explicit, finite decision such as archive, share, conceal, revisit, or defer. Each choice must create a distinct canonical consequence and then close or deliberately schedule a different future event.
- Acceptance test: completing a consequence cannot create an identically structured descendant, and automated traversal cannot generate unbounded `Follow-up:` title nesting.

##### P0 — Build one coherent investigation vertical slice

- An ordinary survey was resolved by scanning to 22%, clicking the first action, scanning to 62%, and immediately clicking the remaining actions, including **Publish the finding**.
- The player did not need to inspect readings, choose evidence, form a hypothesis, decide whether confidence was sufficient, or select what was published.
- Required change: make one encounter family fully evidence-driven before expanding breadth. A recommended ordinary-survey loop is: select the target and suitable instrument, collect readings, inspect named observations, compare or process evidence when needed, choose a supported conclusion, then decide how to record or share it.
- Acceptance test: the final finding depends on selected observations and confidence; unsupported conclusions can be rejected or recorded as uncertain; publishing cannot be completed solely by clicking through thread labels.

##### P1 — Remote contact follow-ups need a real Communications workflow

- After warp, Communications correctly received a delayed message and the thread changed to **Respond to Contact Liaison's follow-up**.
- There was no corresponding remote channel workflow for composing, frequency-addressing, transmitting, waiting, receiving, and translating the response. The remaining interaction was a generic thread action.
- Required change: delayed messages should create a Communications inbox item with sender identity, channel/frequency or relay route, conversation history, delivery state, and a reply control. The resulting transmission event should advance the contact thread.

##### P1 — Activity count currently overstates playable variety

- Generated systems displayed six or seven Activity Board items, but most were passive **Survey body** entries or abstract thread steps.
- Required change: distinguish actionable work from leads. Selecting a survey activity should configure or focus the Science workflow; selecting a contact activity should open Communications; selecting a navigation activity should focus the map. Activities should expose expected evidence, relevant station, current blocker, and completion state.

##### P1 — Situation status needs one authoritative summary

- The individual systems expose state, but the player can still lose track of whether the ship is in contact, waiting for a response, scanning, processing retained data, hostile, cooling, or ready to leave.
- Required change: add a compact current-situation display stating what changed, what is active, what the ship is waiting for, the most important risk, and the next useful station actions. It must derive from simulation state and events rather than generated narration.

##### P2 — Semantic cleanup and presentation verification

- The friendly-contact preset uses the `disputed_boundary` encounter family internally. If family names become player-visible or drive inappropriate actions, use a neutral contact family or a dedicated preset classification.
- Default allocation projected a very small positive heat trend (`+0.032%/s`) while idle. This may be acceptable, but the UI should explain base ship load and show the equilibrium/threshold consequence so it does not look like unexplained damage.
- Re-test the signal-loss workspace reset, warning lights, analogue gauges, sensor fluctuation, movement visualization, ticking sounds, signal playback, and status feedback in the actual browser client. They were outside this command-layer pass.
- Re-test actor and Director variety with the configured local model. The deterministic fallback proved rule safety and state transitions, not narrative quality.

#### Recommended next-session order

1. Replace manual contact-thread advancement with event/evidence-driven completion and invalidate steps that contradict the encounter's current state.
2. Stop recursive follow-up creation and implement finite consequence choices.
3. Complete the ordinary-survey vertical slice from instrument selection through an evidence-backed conclusion.
4. Turn delayed contact follow-ups into a functioning remote Communications conversation.
5. Make Activity Board entries open or focus their owning station workflow and clearly label leads versus immediately actionable tasks.
6. Add the authoritative current-situation summary.
7. Add deterministic regression tests for every issue above.
8. Run a browser-based solo playtest, then run the backend suite, frontend suite, and production build before updating the recorded baseline.

#### Current gameplay assessment

The project has progressed beyond disconnected panels: communications alter persistent actors, Engineering and Tactical systems interact, transit reaches generated encounters, and expedition threads persist. The principal blocker to a genuinely playable minimal loop is now integration. The Activity Board currently describes or directly completes story steps beside the simulation; it must instead interpret evidence produced by the stations and guide the player back into those station workflows.
