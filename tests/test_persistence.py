from pathlib import Path

from space_sim_crew.models import CanonicalEvent
from space_sim_crew.persistence import SaveStore
from space_sim_crew.session import create_game_state


def test_markdown_save_round_trip_and_integrity(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Persistent Reach",
        seed=1234,
        ship_name="Memory",
        crew_capacity=4,
        character_name="Archivist",
        backstory="Keeps careful records.",
    )
    store = SaveStore(tmp_path)
    store.initialize(state, "session_test")
    event = CanonicalEvent(
        universe_id=state.universe_id,
        universe_time_ms=100,
        event_type="test_event",
        source_kind="simulation",
        payload={"proof": "canonical"},
    )
    state.event_count = 1
    state.crew_knowledge.append("A persisted discovery")
    store.commit(state, [event], "session_test")

    loaded = store.load(state.universe_id)
    assert loaded == state
    report = store.verify(state.universe_id)
    assert report["valid"] is True
    assert report["systems"] == 1
    assert report["index_present"] is True
    assert store.search(state.universe_id, "Persistent")[0]["title"] == "Persistent Reach"
    assert "test_event" in next((tmp_path / state.universe_id / "events").glob("*.md")).read_text()
    assert (tmp_path / state.universe_id / "ships" / f"{state.ship.id}.md").read_text().startswith("---\n")
    consistency = (tmp_path / state.universe_id / "knowledge" / "universe-consistency.md").read_text()
    assert "derived diagnostic report" in consistency
    assert "VALID" in consistency
    assert (tmp_path / state.universe_id / "knowledge" / f"{state.world_threads[0].id}.md").exists()


def test_universe_listing_ignores_invalid_directories(tmp_path: Path) -> None:
    (tmp_path / "universe_broken").mkdir()
    store = SaveStore(tmp_path)
    assert store.list_universes() == []
