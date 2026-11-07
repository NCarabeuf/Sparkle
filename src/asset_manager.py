from pathlib import Path

# Get the path to an asset by name.

def get_asset(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / name