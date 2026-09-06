export type AlertSeverity = "status" | "caution" | "critical";
export type MonitorProfile = "auto" | "language" | "telemetry" | "noise";

export function alertKey(alert: { severity: AlertSeverity; source: string; message: string }): string {
  return `${alert.severity}:${alert.source}:${alert.message}`;
}

export function highestAlertSeverity(alerts: Array<{ severity: AlertSeverity }>): AlertSeverity | null {
  if (alerts.some((alert) => alert.severity === "critical")) return "critical";
  if (alerts.some((alert) => alert.severity === "caution")) return "caution";
  if (alerts.some((alert) => alert.severity === "status")) return "status";
  return null;
}

function normalize(samples: number[]): number[] {
  const peak = Math.max(0.001, ...samples.map((sample) => Math.abs(sample)));
  return samples.map((sample) => sample / peak);
}

function correlation(samples: number[], lag: number): number {
  if (lag <= 0 || lag >= samples.length) return 0;
  let numerator = 0;
  let leftPower = 0;
  let rightPower = 0;
  for (let index = lag; index < samples.length; index += 1) {
    const left = samples[index];
    const right = samples[index - lag];
    numerator += left * right;
    leftPower += left * left;
    rightPower += right * right;
  }
  return numerator / Math.max(1e-9, Math.sqrt(leftPower * rightPower));
}

/**
 * Classify only the audible presentation of a receiver trace. This never changes
 * the scientific samples or analysis. It gives the monitor a plausible acoustic
 * character instead of replaying a 64 Hz trace as a buzzy tone.
 */
export function classifyMonitorProfile(samples: number[]): Exclude<MonitorProfile, "auto"> {
  if (samples.length < 8) return "telemetry";
  const values = normalize(samples);
  let derivativeEnergy = 0;
  let impulseCount = 0;
  let zeroCrossings = 0;
  let envelopeChange = 0;
  for (let index = 1; index < values.length; index += 1) {
    const delta = values[index] - values[index - 1];
    derivativeEnergy += Math.abs(delta);
    envelopeChange += Math.abs(Math.abs(values[index]) - Math.abs(values[index - 1]));
    if (Math.abs(delta) > 1.15) impulseCount += 1;
    if ((values[index] >= 0) !== (values[index - 1] >= 0)) zeroCrossings += 1;
  }
  const impulseRatio = impulseCount / Math.max(1, values.length - 1);
  const crossingRatio = zeroCrossings / Math.max(1, values.length - 1);
  const roughness = derivativeEnergy / Math.max(1, values.length - 1);
  const envelopeVariation = envelopeChange / Math.max(1, values.length - 1);
  let periodicity = 0;
  for (let lag = 2; lag <= Math.min(24, Math.floor(values.length / 3)); lag += 1) {
    periodicity = Math.max(periodicity, Math.abs(correlation(values, lag)));
  }

  if (periodicity < 0.22 && roughness > 0.42) return "noise";
  if (impulseRatio > 0.08 || crossingRatio > 0.52 || (periodicity > 0.72 && envelopeVariation < 0.2)) return "telemetry";
  return "language";
}

function sampleControl(samples: number[], sourceRateHz: number, timeSeconds: number, speed = 1): number {
  const position = (timeSeconds * sourceRateHz * speed) % samples.length;
  const left = Math.floor(position);
  const right = (left + 1) % samples.length;
  const fraction = position - left;
  return samples[left] * (1 - fraction) + samples[right] * fraction;
}

function seededNoiseFactory(samples: number[]): () => number {
  let state = 2166136261 >>> 0;
  for (const sample of samples) {
    state ^= Math.round((sample + 2) * 100000) >>> 0;
    state = Math.imul(state, 16777619) >>> 0;
  }
  return () => {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return (((value ^ (value >>> 14)) >>> 0) / 4294967296) * 2 - 1;
  };
}

function renderLanguageMonitor(samples: number[], sourceRateHz: number, outputRateHz: number, output: Float32Array): void {
  const noise = seededNoiseFactory(samples);
  let fundamentalPhase = 0;
  let formantOnePhase = 0;
  let formantTwoPhase = 0;
  let formantThreePhase = 0;
  let previousControl = 0;
  for (let index = 0; index < output.length; index += 1) {
    const time = index / outputRateHz;
    const control = sampleControl(samples, sourceRateHz, time, 0.76);
    const slow = sampleControl(samples, sourceRateHz, time + 0.11, 0.19);
    const derivative = Math.min(1, Math.abs(control - previousControl) * 2.4);
    previousControl = control;

    const syllableRate = 3.0 + 0.9 * Math.abs(slow);
    const syllablePhase = (time * syllableRate + 0.08 * control) % 1;
    const syllableEnvelope = Math.pow(Math.max(0, Math.sin(Math.PI * syllablePhase)), 0.65);
    const phrasePause = Math.sin(2 * Math.PI * (0.42 + 0.05 * slow) * time) < -0.78 ? 0.18 : 1;
    const envelope = syllableEnvelope * phrasePause * (0.48 + 0.5 * Math.min(1, Math.abs(control) + 0.25));

    const fundamental = 105 + 68 * (control * 0.5 + 0.5) + 8 * Math.sin(2 * Math.PI * 0.65 * time);
    const formantOne = 430 + 220 * (slow * 0.5 + 0.5);
    const formantTwo = 1250 + 620 * (control * 0.5 + 0.5);
    const formantThree = 2380 + 260 * Math.sin(2 * Math.PI * 0.23 * time + control);
    fundamentalPhase += 2 * Math.PI * fundamental / outputRateHz;
    formantOnePhase += 2 * Math.PI * formantOne / outputRateHz;
    formantTwoPhase += 2 * Math.PI * formantTwo / outputRateHz;
    formantThreePhase += 2 * Math.PI * formantThree / outputRateHz;

    const voiced = Math.sin(fundamentalPhase)
      + 0.42 * Math.sin(2 * fundamentalPhase)
      + 0.2 * Math.sin(3 * fundamentalPhase);
    const formants = 0.58 * Math.sin(formantOnePhase)
      + 0.35 * Math.sin(formantTwoPhase)
      + 0.16 * Math.sin(formantThreePhase);
    const fricative = noise() * derivative * (0.2 + 0.25 * syllableEnvelope);
    const radioNoise = noise() * 0.045;
    output[index] = envelope * (0.33 * voiced + 0.38 * formants + fricative) + radioNoise;
  }
}

function renderTelemetryMonitor(samples: number[], sourceRateHz: number, outputRateHz: number, output: Float32Array): void {
  const noise = seededNoiseFactory(samples);
  let phase = 0;
  let subPhase = 0;
  for (let index = 0; index < output.length; index += 1) {
    const time = index / outputRateHz;
    const control = sampleControl(samples, sourceRateHz, time, 1.35);
    const delayed = sampleControl(samples, sourceRateHz, time + 0.07, 0.63);
    const bit = control >= 0 ? 1 : -1;
    const carrier = 610 + bit * 170 + delayed * 95;
    const subcarrier = 1210 + 210 * control;
    phase += 2 * Math.PI * carrier / outputRateHz;
    subPhase += 2 * Math.PI * subcarrier / outputRateHz;
    const pulseGate = Math.abs(control) > 0.16 ? 1 : 0.15;
    const chirp = Math.sin(phase + 0.55 * Math.sin(2 * Math.PI * 1.7 * time));
    const clock = Math.sin(subPhase) > 0.55 ? 0.22 : 0;
    const click = Math.abs(control - delayed) > 0.85 ? noise() * 0.18 : 0;
    output[index] = pulseGate * (0.48 * chirp + clock) + click + noise() * 0.05;
  }
}

function renderNoiseMonitor(samples: number[], sourceRateHz: number, outputRateHz: number, output: Float32Array): void {
  const noise = seededNoiseFactory(samples);
  let previous = 0;
  let rumblePhase = 0;
  for (let index = 0; index < output.length; index += 1) {
    const time = index / outputRateHz;
    const control = sampleControl(samples, sourceRateHz, time, 0.48);
    const white = noise();
    previous = previous * 0.86 + white * 0.14;
    rumblePhase += 2 * Math.PI * (46 + 22 * Math.abs(control)) / outputRateHz;
    const hiss = 0.24 * white + 0.42 * previous;
    const rumble = Math.sin(rumblePhase) * (0.12 + 0.2 * Math.abs(control));
    const sporadic = Math.abs(control) > 0.82 ? noise() * 0.2 : 0;
    output[index] = hiss + rumble + sporadic;
  }
}

/**
 * Render a plausible audible receiver monitor from the low-rate scientific trace.
 * The scientific samples remain untouched; this is presentation-only audio.
 */
export function buildAudibleMonitor(
  samples: number[],
  sourceRateHz: number,
  outputRateHz: number,
  durationSeconds = 3,
  _frequencyShift = 18,
  requestedProfile: MonitorProfile = "auto",
): Float32Array {
  if (!samples.length || sourceRateHz <= 0 || outputRateHz <= 0 || durationSeconds <= 0) return new Float32Array();
  const normalized = normalize(samples);
  const output = new Float32Array(Math.floor(outputRateHz * durationSeconds));
  const profile = requestedProfile === "auto" ? classifyMonitorProfile(normalized) : requestedProfile;
  if (profile === "language") renderLanguageMonitor(normalized, sourceRateHz, outputRateHz, output);
  else if (profile === "noise") renderNoiseMonitor(normalized, sourceRateHz, outputRateHz, output);
  else renderTelemetryMonitor(normalized, sourceRateHz, outputRateHz, output);

  const peak = Math.max(0.001, ...output.map((sample) => Math.abs(sample)));
  const fadeSamples = Math.max(1, Math.floor(outputRateHz * 0.035));
  for (let index = 0; index < output.length; index += 1) {
    const fadeIn = Math.min(1, index / fadeSamples);
    const fadeOut = Math.min(1, (output.length - 1 - index) / fadeSamples);
    output[index] = output[index] / peak * 0.32 * Math.max(0, Math.min(fadeIn, fadeOut));
  }
  return output;
}

function tone(
  context: AudioContext,
  start: number,
  frequency: number,
  duration: number,
  volume: number,
  waveform: OscillatorType = "sine",
): void {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = waveform;
  oscillator.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start(start);
  oscillator.stop(start + duration + 0.01);
}

export function playAlertTone(context: AudioContext, severity: AlertSeverity): void {
  const now = context.currentTime + 0.015;
  if (severity === "critical") {
    tone(context, now, 820, 0.22, 0.11, "square");
    tone(context, now + 0.28, 820, 0.22, 0.11, "square");
    tone(context, now + 0.56, 820, 0.22, 0.11, "square");
  } else if (severity === "caution") {
    tone(context, now, 620, 0.16, 0.08, "triangle");
    tone(context, now + 0.2, 470, 0.22, 0.08, "triangle");
  } else {
    tone(context, now, 740, 0.08, 0.045, "sine");
  }
}

export function playClockTick(context: AudioContext): void {
  const now = context.currentTime + 0.005;
  tone(context, now, 1150, 0.025, 0.025, "square");
}

export function playMonitorBuffer(
  context: AudioContext,
  samples: number[],
  sourceRateHz: number,
  profile: MonitorProfile = "auto",
): AudioBufferSourceNode | null {
  const monitor = buildAudibleMonitor(samples, sourceRateHz, context.sampleRate, 3, 18, profile);
  if (!monitor.length) return null;
  const buffer = context.createBuffer(1, monitor.length, context.sampleRate);
  buffer.getChannelData(0).set(monitor);
  const source = context.createBufferSource();
  source.buffer = buffer;
  const highpass = context.createBiquadFilter();
  highpass.type = "highpass";
  highpass.frequency.value = 120;
  const lowpass = context.createBiquadFilter();
  lowpass.type = "lowpass";
  lowpass.frequency.value = 4200;
  const gain = context.createGain();
  gain.gain.value = 0.9;
  source.connect(highpass).connect(lowpass).connect(gain).connect(context.destination);
  source.start();
  return source;
}
