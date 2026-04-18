import os

FUNCTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "functions.py")


def _read_functions():
    with open(FUNCTIONS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def test_spotify_callback_route_is_present():
    content = _read_functions()
    assert 'parsed.path == "/spotify/callback"' in content
    assert "consume_spotify_auth_result" in content


def test_spotify_state_mismatch_guard_exists():
    content = _read_functions()
    assert "state_mismatch" in content
