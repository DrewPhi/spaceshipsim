from __future__ import annotations

import math
import random
from typing import Any


RECIPE_LIMITS = {
    "center_frequency_mhz": (100.0, 3000.0),
    "carrier_hz": (3.0, 22.0),
    "modulation_hz": (0.15, 3.0),
    "drift_hz_s": (-0.8, 0.8),
    "correlated_noise": (0.1, 2.5),
    "impulse_rate_hz": (0.0, 5.0),
    "nonlinear_noise": (0.0, 1.5),
}


def default_signal_recipe(seed: int, family: str) -> dict[str, Any]:
    rng = random.Random(f"signal:{seed}:{family}")
    payloads = {
        "artificial_signal": "Repeated identification request. Confirm reception and state your origin and purpose.",
        "damaged_vessel": "Automated emergency beacon. Propulsion disabled. Life-support margin decreasing.",
        "disputed_boundary": "Identification and course declaration required before further approach.",
        "ancient_site": "A repeating telemetry sequence with no recognized addressing or language layer.",
        "environmental_hazard": "No stable information-bearing frame detected.",
        "ordinary_survey": "No stable information-bearing frame detected.",
    }
    return {
        "center_frequency_mhz": round(rng.uniform(400, 2400), 3),
        "carrier_hz": round(rng.uniform(6, 15), 3),
        "modulation_hz": round(rng.uniform(0.35, 1.8), 3),
        "drift_hz_s": round(rng.uniform(-0.22, 0.22), 4),
        "correlated_noise": round(rng.uniform(0.7, 1.8), 3),
        "impulse_rate_hz": round(rng.uniform(0.2, 2.2), 3),
        "nonlinear_noise": round(rng.uniform(0.25, 1.0), 3),
        "signal_kind": "noise_like" if family in {"ordinary_survey", "environmental_hazard"} else "structured",
        "modulation": rng.choice(("amplitude", "frequency", "phase_shift", "pulse")),
        "payload": payloads.get(family, "A structured sequence repeats without a known interpretation."),
    }


def validate_signal_recipe(candidate: Any, seed: int, family: str) -> dict[str, Any]:
    fallback = default_signal_recipe(seed, family)
    if not isinstance(candidate, dict):
        return fallback
    validated: dict[str, Any] = {}
    for name, (minimum, maximum) in RECIPE_LIMITS.items():
        try:
            value = float(candidate.get(name, fallback[name]))
        except (TypeError, ValueError):
            value = fallback[name]
        validated[name] = round(min(maximum, max(minimum, value)), 5)
    kind = str(candidate.get("signal_kind", fallback["signal_kind"]))
    validated["signal_kind"] = kind if kind in {"noise_like", "structured"} else fallback["signal_kind"]
    modulation = str(candidate.get("modulation", fallback["modulation"]))
    validated["modulation"] = modulation if modulation in {"amplitude", "frequency", "phase_shift", "pulse"} else fallback["modulation"]
    payload = str(candidate.get("payload", fallback["payload"])).strip()
    validated["payload"] = (payload or str(fallback["payload"]))[:240]
    return validated


def synthesize_signal(recipe: dict[str, Any], seed: int, sample_rate_hz: int = 64, sample_count: int = 192) -> dict[str, Any]:
    rng = random.Random(f"samples:{seed}:{sorted(recipe.items())}")
    channels: list[list[float]] = []
    times = [index / sample_rate_hz for index in range(sample_count)]
    clean: list[float] = []
    common_artifact: list[float] = []
    impulses = [0.0] * sample_count
    impulse_probability = recipe["impulse_rate_hz"] / sample_rate_hz
    for index, time_s in enumerate(times):
        phase = 2 * math.pi * (recipe["carrier_hz"] * time_s + 0.5 * recipe["drift_hz_s"] * time_s**2)
        symbol = 1 if math.sin(2 * math.pi * recipe["modulation_hz"] * time_s) >= 0 else -1
        if recipe["signal_kind"] == "noise_like":
            information = rng.gauss(0, .18)
        elif recipe["modulation"] == "amplitude":
            information = math.sin(phase) * (0.68 + 0.24 * symbol)
        elif recipe["modulation"] == "frequency":
            information = math.sin(phase + symbol * 2 * math.pi * .22 * time_s)
        elif recipe["modulation"] == "pulse":
            information = math.sin(phase) * (1 if symbol > 0 and (time_s * recipe["carrier_hz"]) % 1 < .45 else .08)
        else:
            information = math.sin(phase + symbol * 0.42) * (0.72 + 0.18 * symbol)
        clean.append(information)
        base = math.sin(2 * math.pi * 0.73 * time_s + 0.35 * math.sin(2 * math.pi * 0.19 * time_s))
        common_artifact.append(recipe["correlated_noise"] * base)
        if rng.random() < impulse_probability:
            impulses[index] = rng.choice((-1.0, 1.0)) * rng.uniform(1.2, 2.5)
    mix_clean = (1.0, 0.72, -0.48, 0.31)
    mix_artifact = (1.0, 0.91, 1.13, 0.82)
    for channel_index in range(4):
        channel: list[float] = []
        for index, time_s in enumerate(times):
            independent = rng.gauss(0, 0.13 + channel_index * 0.018)
            curved = recipe["nonlinear_noise"] * (common_artifact[index] ** 2 - recipe["correlated_noise"] ** 2 / 2)
            value = (
                mix_clean[channel_index] * clean[index]
                + mix_artifact[channel_index] * common_artifact[index]
                + (0.22 + channel_index * 0.07) * curved
                + impulses[index] * (1 - channel_index * 0.12)
                + independent
            )
            channel.append(round(value, 5))
        channels.append(channel)
    return {"sample_rate_hz": sample_rate_hz, "times": times, "channels": channels}


def _jacobi_eigen(matrix: list[list[float]], iterations: int = 80) -> tuple[list[float], list[list[float]]]:
    size = len(matrix)
    values = [row[:] for row in matrix]
    vectors = [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]
    for _ in range(iterations):
        p, q = 0, 1 if size > 1 else 0
        largest = 0.0
        for row in range(size):
            for column in range(row + 1, size):
                if abs(values[row][column]) > largest:
                    largest = abs(values[row][column])
                    p, q = row, column
        if largest < 1e-10:
            break
        angle = 0.5 * math.atan2(2 * values[p][q], values[q][q] - values[p][p])
        cosine, sine = math.cos(angle), math.sin(angle)
        for index in range(size):
            if index not in (p, q):
                old_p, old_q = values[index][p], values[index][q]
                values[index][p] = values[p][index] = cosine * old_p - sine * old_q
                values[index][q] = values[q][index] = sine * old_p + cosine * old_q
        old_pp, old_qq, old_pq = values[p][p], values[q][q], values[p][q]
        values[p][p] = cosine**2 * old_pp - 2 * sine * cosine * old_pq + sine**2 * old_qq
        values[q][q] = sine**2 * old_pp + 2 * sine * cosine * old_pq + cosine**2 * old_qq
        values[p][q] = values[q][p] = 0.0
        for index in range(size):
            old_p, old_q = vectors[index][p], vectors[index][q]
            vectors[index][p] = cosine * old_p - sine * old_q
            vectors[index][q] = sine * old_p + cosine * old_q
    order = sorted(range(size), key=lambda index: values[index][index], reverse=True)
    return [values[index][index] for index in order], [[vectors[row][index] for row in range(size)] for index in order]


def pca_analysis(signal: dict[str, Any], cutoff: int, selected_side: str) -> dict[str, Any]:
    channels: list[list[float]] = signal["channels"]
    rows = [list(values) for values in zip(*channels, strict=True)]
    dimensions = len(channels)
    means = [sum(row[column] for row in rows) / len(rows) for column in range(dimensions)]
    deviations = [
        max(1e-8, math.sqrt(sum((row[column] - means[column]) ** 2 for row in rows) / (len(rows) - 1)))
        for column in range(dimensions)
    ]
    standardized = [[(row[column] - means[column]) / deviations[column] for column in range(dimensions)] for row in rows]
    covariance = [[sum(row[a] * row[b] for row in standardized) / (len(rows) - 1) for b in range(dimensions)] for a in range(dimensions)]
    eigenvalues, eigenvectors = _jacobi_eigen(covariance)
    cutoff = max(1, min(dimensions - 1, cutoff))
    selected = set(range(cutoff)) if selected_side == "high_variance" else set(range(cutoff, dimensions))
    reconstructed: list[list[float]] = []
    for row in standardized:
        scores = [sum(row[index] * vector[index] for index in range(dimensions)) for vector in eigenvectors]
        for index in range(dimensions):
            if index not in selected:
                scores[index] = 0.0
        restored = [sum(scores[component] * eigenvectors[component][column] for component in range(dimensions)) for column in range(dimensions)]
        reconstructed.append([restored[column] * deviations[column] + means[column] for column in range(dimensions)])
    total = max(1e-9, sum(max(0, value) for value in eigenvalues))
    return {
        "eigenvalues": [round(max(0, value), 5) for value in eigenvalues],
        "explained_variance": [round(max(0, value) / total, 5) for value in eigenvalues],
        "loadings": [[round(value, 5) for value in vector] for vector in eigenvectors],
        "cutoff": cutoff,
        "selected_side": "high_variance" if selected_side == "high_variance" else "low_variance",
        "raw_preview": [round(row[0], 4) for row in rows],
        "reconstructed_preview": [round(row[0], 4) for row in reconstructed],
        "reconstructed_channels": [[row[column] for row in reconstructed] for column in range(dimensions)],
    }


def spectrogram(signal: dict[str, Any], window_size: int = 32, hop: int = 8) -> dict[str, Any]:
    samples: list[float] = signal["channels"][0]
    frames: list[list[float]] = []
    for start in range(0, len(samples) - window_size + 1, hop):
        window = [samples[start + index] * (0.5 - 0.5 * math.cos(2 * math.pi * index / (window_size - 1))) for index in range(window_size)]
        bins: list[float] = []
        for frequency_bin in range(window_size // 2):
            real = sum(value * math.cos(-2 * math.pi * frequency_bin * index / window_size) for index, value in enumerate(window))
            imaginary = sum(value * math.sin(-2 * math.pi * frequency_bin * index / window_size) for index, value in enumerate(window))
            bins.append(math.sqrt(real * real + imaginary * imaginary))
        frames.append(bins)
    peak = max((value for frame in frames for value in frame), default=1.0)
    return {
        "window_size": window_size,
        "hop_size": hop,
        "frequency_bin_hz": signal["sample_rate_hz"] / window_size,
        "frames": [[round(value / peak, 4) for value in frame] for frame in frames],
    }


def _power_eigenvectors(matrix: list[list[float]], count: int) -> tuple[list[float], list[list[float]]]:
    size = len(matrix)
    vectors: list[list[float]] = []
    eigenvalues: list[float] = []
    for component in range(count):
        vector = [math.sin((index + 1) * (component + 1) * 1.731) for index in range(size)]
        for _ in range(70):
            candidate = [sum(matrix[row][column] * vector[column] for column in range(size)) for row in range(size)]
            for previous in vectors:
                projection = sum(candidate[index] * previous[index] for index in range(size))
                candidate = [candidate[index] - projection * previous[index] for index in range(size)]
            norm = math.sqrt(sum(value * value for value in candidate)) or 1.0
            vector = [value / norm for value in candidate]
        eigenvalue = sum(vector[row] * sum(matrix[row][column] * vector[column] for column in range(size)) for row in range(size))
        vectors.append(vector)
        eigenvalues.append(eigenvalue)
    return eigenvalues, vectors


def diffusion_maps(signal: dict[str, Any], pca: dict[str, Any], epsilon: float, diffusion_time: int, neighbors: int) -> dict[str, Any]:
    channels: list[list[float]] = pca["reconstructed_channels"]
    stride = 4
    points = [list(values) for values in zip(*(channel[::stride] for channel in channels), strict=True)]
    count = len(points)
    distances = [[sum((points[a][d] - points[b][d]) ** 2 for d in range(len(channels))) for b in range(count)] for a in range(count)]
    nonzero = sorted(distance for row in distances for distance in row if distance > 0)
    scale = nonzero[len(nonzero) // 2] if nonzero else 1.0
    bandwidth = max(1e-6, epsilon * scale)
    kernel = [[math.exp(-distances[row][column] / bandwidth) for column in range(count)] for row in range(count)]
    degrees = [sum(row) for row in kernel]
    symmetric = [[kernel[row][column] / math.sqrt(max(1e-12, degrees[row] * degrees[column])) for column in range(count)] for row in range(count)]
    eigenvalues, eigenvectors = _power_eigenvectors(symmetric, min(4, count))
    diffusion_time = max(1, min(8, diffusion_time))
    coordinates = []
    for index in range(count):
        coordinates.append({
            "time_s": round(signal["times"][index * stride], 4),
            "x": round((eigenvalues[1] ** diffusion_time) * eigenvectors[1][index], 6) if len(eigenvalues) > 1 else 0,
            "y": round((eigenvalues[2] ** diffusion_time) * eigenvectors[2][index], 6) if len(eigenvalues) > 2 else 0,
            "amplitude": round(points[index][0], 5),
        })
    neighbors = max(2, min(12, neighbors))
    denoised: list[float] = []
    for index, coordinate in enumerate(coordinates):
        nearest = sorted(
            range(count),
            key=lambda other: (coordinate["x"] - coordinates[other]["x"]) ** 2 + (coordinate["y"] - coordinates[other]["y"]) ** 2,
        )[:neighbors]
        denoised.append(round(sum(points[other][0] for other in nearest) / len(nearest), 5))
    radii = [math.hypot(coordinate["x"], coordinate["y"]) for coordinate in coordinates]
    sorted_radii = sorted(radii)
    median_radius = sorted_radii[len(sorted_radii) // 2] if sorted_radii else 0
    deviations = sorted(abs(value - median_radius) for value in radii)
    median_deviation = deviations[len(deviations) // 2] if deviations else 0
    outlier_threshold = median_radius + max(1e-8, 2.8 * median_deviation)
    outlier_indices = [index for index, radius in enumerate(radii) if radius > outlier_threshold]
    consecutive = [
        math.hypot(coordinates[index]["x"] - coordinates[index - 1]["x"], coordinates[index]["y"] - coordinates[index - 1]["y"])
        for index in range(1, len(coordinates))
    ]
    continuity = 1 / (1 + (sum(consecutive) / max(1, len(consecutive))) / max(1e-8, median_radius))
    nontrivial = eigenvalues[1:] if len(eigenvalues) > 1 else []
    gaps = [nontrivial[index] - nontrivial[index + 1] for index in range(len(nontrivial) - 1)]
    dominant_dimensions = (gaps.index(max(gaps)) + 1) if gaps else len(nontrivial)
    if len(outlier_indices) > count * .3:
        interpretation = "Many samples are isolated; increase kernel bandwidth before classifying clusters."
    elif not outlier_indices:
        interpretation = "No samples separate from the main trajectory; reduce kernel bandwidth if impulses are still visible in the waveform."
    else:
        interpretation = "A connected main trajectory and isolated samples are visible; compare isolated times with waveform impulses before classifying them as artifacts."
    return {
        "eigenvalues": [round(value, 6) for value in eigenvalues],
        "epsilon": epsilon,
        "diffusion_time": diffusion_time,
        "neighbors": neighbors,
        "embedding": coordinates,
        "denoised_preview": denoised,
        "outlier_indices": outlier_indices,
        "outlier_fraction": round(len(outlier_indices) / max(1, count), 4),
        "temporal_continuity": round(continuity, 4),
        "dominant_dimensions": dominant_dimensions,
        "interpretation": interpretation,
    }
