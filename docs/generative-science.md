# Generative Science

StarTrekSim's scientific-discovery layer follows one hard rule:

> **The AI may invent the scientific rule before an experiment; deterministic simulation decides what the experiment actually observes.**

This keeps the Universe God creative without allowing post-hoc narrative answers to rewrite physical truth.

## Scientific canon

Each universe has a second inspectable knowledge document:

`knowledge/scientific-canon.md`

It records:

- AI-authored phenomenon blueprints
- their hidden mechanisms
- falsifiable predictions
- which predictions the crew actually verified
- generated scientific capabilities that became part of the ship
- a persistent novelty budget

Verified findings are also promoted into director-only narrative canon so future Universe God generation can build on prior discoveries without making unrelated NPCs omniscient.

## Phenomenon proposal grammar

The Science Architect may return no special phenomenon at all. When it does create one, it composes a small deterministic primitive vocabulary rather than arbitrary code.

Mechanic primitives currently include:

- `operator_eigenstructure`
- `phase_coupling`
- `recurrence_structure`
- `scale_dependent_state`
- `cross_domain_relation`
- `stimulus_response`

Analysis primitives available to its predictions include:

- spectrogram
- autocorrelation
- cross-correlation
- delay embedding
- diffusion maps
- recurrence analysis
- phase coherence
- entropy
- clustering

A generated prediction must name a numeric metric and threshold/range. Supported metrics currently include motif recovery, autocorrelation peak, cross-channel correlation, recurrence density, entropy, diffusion-map temporal continuity, outlier fraction, and dominant dimensionality.

## Diffusion geometry

Universe God sessions no longer require PCA to establish a usable structured carrier. Communications can test and demodulate the raw recording directly, while Science uses Diffusion Maps on the raw multichannel state vectors.

`operator_eigenstructure` is the deliberately unusual case. The AI may invent a set of normalized latent motif points. The deterministic runtime converts the requested geometry into a stochastic transition operator whose first non-trivial eigenspace carries that geometry. The client then displays the computed diffusion coordinates; it does not paint an AI-authored glyph over the plot.

The recovery score is based on pairwise-distance agreement, so ordinary spectral rotations and reflections do not count as failures. The mechanic can also specify an ideal kernel bandwidth and tolerance, allowing a motif to emerge only over an appropriate analysis scale.

The motif does not have to be a glyph. The AI can use the same mechanism for an abstract geometric signature, a map-like path, a mathematical construction, an identity mark, or another idea consistent with the encounter.

## Generated capabilities

A phenomenon may optionally propose a capability blueprint. It is validated against installed domains, bounded power requirements, a permitted analysis-operation list, and explicit prerequisites. Dangerous outputs such as weapons, arbitrary damage, teleportation, free energy, or unrestricted repair are rejected.

Capabilities can be acquired as software, a field modification, or salvage. They are installed only after their required scientific predictions have actually been verified (and, for salvage, after the recovery event). Once installed they become normal persistent `Capability` objects on the ship and are visible to later AI-authored science as part of the crew's real equipment history.

## Novelty budget

Scientific weirdness is intentionally scarce. The persistent budget charges more for unusual, exotic, and unprecedented phenomena, while encounters in which the model chooses ordinary science slowly replenish it. This is intended to keep a diffusion-space inscription or improvised alien instrument memorable rather than making every system a puzzle box.

## Current boundary

The grammar is deliberately bounded rather than arbitrary code generation. Adding a new scientific primitive means implementing a deterministic executor and measurable outputs first; only then can the Universe God compose it. The goal is to grow this vocabulary over time while retaining reproducibility, save integrity, and a clear distinction between authored hypotheses and observed results.
