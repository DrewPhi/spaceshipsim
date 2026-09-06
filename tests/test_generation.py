from space_sim_crew.generation import generate_encounter, generate_system, system_id


def test_system_generation_is_stable_and_unbounded() -> None:
    seed = 982_451_653
    systems = [generate_system(seed, (index, -index)) for index in range(50)]
    assert len({system.id for system in systems}) == 50
    assert generate_system(seed, (12, -12)) == systems[12]
    assert system_id(seed, (999_999, -999_999)).startswith("system_")
    assert all(len(system.neighbor_coordinates) == 4 for system in systems)


def test_encounters_are_stable_and_cover_valid_family() -> None:
    system = generate_system(42, (4, 7))
    first = generate_encounter(42, system)
    second = generate_encounter(42, system)
    # Runtime encounter IDs differ, but content derived from the universe does not.
    assert first.family == second.family
    assert first.title == second.title
    assert first.hidden_truth == second.hidden_truth
    assert first.target_id == second.target_id

