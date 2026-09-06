export type AlertSeverity = "status" | "caution" | "critical";

export function alertKey(alert: { severity: AlertSeverity; source: string; message: string }): string {
  return `${alert.severity}:${alert.source}:${alert.message}`;
}

export function highestAlertSeverity(alerts: Array<{ severity: AlertSeverity }>): AlertSeverity | null {
  if (alerts.some((alert) => alert.severity === "critical")) return "critical";
  if (alerts.some((alert) => alert.severity === "caution")) return "caution";
  if (alerts.some((alert) => alert.severity === "status")) return "status";
  return null;
}

/**
 * Converts low-rate receiver/baseband samples into an audible monitor.
 * This is intentionally a frequency-shifted monitor, not decoded speech.
 */
export function buildAudibleMonitor(
  samples: number[],
  sourceRateHz: number,
  outputRateHz: number,
  durationSeconds = 3,
  frequencyShift = 18,
): Float32Array {
  if (!samples.length || sourceRateHz <= 0 || outputRateHz <= 0 || durationSeconds <= 0) return new Float32Array();
  const output = new Float32Array(Math.floor(outputRateHz * durationSeconds));
  const peak = Math.max(0.001, ...samples.map((sample) => Math.abs(sample)));
  const fadeSamples = Math.max(1, Math.floor(outputRateHz * 0.03));

  for (let index = 0; index < output.length; index += 1) {
    const sourcePosition = (index * sourceRateHz * frequencyShift / outputRateHz) % samples.length;
    const leftIndex = Math.floor(sourcePosition);
    const rightIndex = (leftIndex + 1) % samples.length;
    const fraction = sourcePosition - leftIndex;
    const interpolated = samples[leftIndex] * (1 - fraction) + samples[rightIndex] * fraction;
    const fadeIn = Math.min(1, index / fadeSamples);
    const fadeOut = Math.min(1, (output.length - 1 - index) / fadeSamples);
    output[index] = interpolated / peak * 0.32 * Math.max(0, Math.min(fadeIn, fadeOut));
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

export function playMonitorBuffer(context: AudioContext, samples: number[], sourceRateHz: number): AudioBufferSourceNode | null {
  const monitor = buildAudibleMonitor(samples, sourceRateHz, context.sampleRate);
  if (!monitor.length) return null;
  const buffer = context.createBuffer(1, monitor.length, context.sampleRate);
  buffer.getChannelData(0).set(monitor);
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  source.start();
  return source;
}
