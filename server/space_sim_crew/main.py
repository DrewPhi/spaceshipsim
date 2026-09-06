from __future__ import annotations

import os

import uvicorn


def run() -> None:
    uvicorn.run(
        "space_sim_crew.api:app",
        host=os.getenv("SPACE_CREW_HOST", "0.0.0.0"),
        port=int(os.getenv("SPACE_CREW_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
