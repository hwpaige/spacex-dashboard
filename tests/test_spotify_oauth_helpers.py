import os
import sys

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import functions as funcs


def test_spotify_auth_result_round_trip():
    funcs.reset_spotify_auth_result()
    funcs._set_spotify_auth_result({"code": "abc", "state": "xyz", "error": ""})
    payload = funcs.consume_spotify_auth_result(expected_state="xyz")
    assert payload["code"] == "abc"
    assert funcs.consume_spotify_auth_result() is None


def test_spotify_state_mismatch_guard_blocks_payload():
    funcs.reset_spotify_auth_result()
    funcs._set_spotify_auth_result({"code": "abc", "state": "wrong", "error": ""})
    payload = funcs.consume_spotify_auth_result(expected_state="expected")
    assert payload["error"] == "state_mismatch"
    assert funcs.consume_spotify_auth_result() is None
