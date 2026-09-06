from space_sim_crew.signal_processing import default_signal_recipe, diffusion_maps, pca_analysis, spectrogram, synthesize_signal, validate_signal_recipe


def test_signal_recipe_is_bounded_and_synthesis_is_deterministic() -> None:
    recipe = validate_signal_recipe({"carrier_hz": 999, "correlated_noise": -4}, 42, "artificial_signal")
    assert recipe["carrier_hz"] == 22
    assert recipe["correlated_noise"] == .1
    assert synthesize_signal(recipe, 42) == synthesize_signal(recipe, 42)


def test_pca_spectrogram_and_diffusion_maps_produce_finite_products() -> None:
    signal = synthesize_signal(default_signal_recipe(7, "artificial_signal"), 7)
    pca = pca_analysis(signal, 1, "low_variance")
    spectrum = spectrogram(signal)
    embedding = diffusion_maps(signal, pca, epsilon=1, diffusion_time=2, neighbors=5)
    assert pca["eigenvalues"] == sorted(pca["eigenvalues"], reverse=True)
    assert len(pca["reconstructed_preview"]) == 192
    assert spectrum["frames"] and len(spectrum["frames"][0]) == 16
    assert len(embedding["embedding"]) == 48
    assert len(embedding["denoised_preview"]) == 48
    assert embedding["interpretation"]
    assert 0 <= embedding["outlier_fraction"] <= 1
