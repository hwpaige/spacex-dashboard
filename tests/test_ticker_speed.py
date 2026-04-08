"""Tests that validate the ticker scroll-speed fix in src/ui_qml.py.

The ticker used to have a fixed duration of 1,600,000 ms regardless of text
width.  When the text content changed after boot (API data loaded with a
different number of items), the scrolling speed would change because
speed = distance / duration and only the distance was variable.

The fix:
  1. duration is now computed as  distance / 0.025  (≈ 25 px/s constant speed)
  2. onTextChanged restarts the animation so a mid-animation width change does
     not leave the ticker crawling at the wrong speed.
"""

import re
from pathlib import Path

UI_QML_PATH = Path(__file__).parent.parent / 'src' / 'ui_qml.py'


def _read_ui():
    return UI_QML_PATH.read_text(encoding='utf-8')


def test_ticker_duration_is_not_fixed():
    """The old hard-coded duration: 1600000 must be gone."""
    src = _read_ui()
    assert 'duration: 1600000' not in src, (
        "Ticker still has a fixed duration: 1600000.  "
        "It must be replaced with a dynamic expression."
    )


def test_ticker_duration_uses_text_width():
    """duration must reference tickerText.width so speed scales with content."""
    src = _read_ui()
    # Find the SequentialAnimation block for the ticker
    ticker_block_start = src.find('id: tickerScrollSequence')
    assert ticker_block_start != -1, "tickerScrollSequence animation not found"
    # Within a reasonable window after the id, duration must use tickerText.width
    window = src[ticker_block_start:ticker_block_start + 600]
    assert 'tickerText.width' in window, (
        "Ticker duration does not reference tickerText.width; "
        "speed will not scale with text length."
    )


def test_ticker_duration_uses_constant_speed_divisor():
    """duration must be  distance / <speed_constant>  not an arbitrary large number."""
    src = _read_ui()
    ticker_block_start = src.find('id: tickerScrollSequence')
    assert ticker_block_start != -1, "tickerScrollSequence animation not found"
    window = src[ticker_block_start:ticker_block_start + 600]
    # The divisor 0.025 encodes the intended scroll speed: 0.025 px/ms = 25 px/s
    assert '0.025' in window, (
        "Ticker duration formula does not use the 0.025 px/ms speed constant."
    )


def test_ticker_animation_has_id():
    """The SequentialAnimation needs an id so onTextChanged can call restart()."""
    src = _read_ui()
    assert 'id: tickerScrollSequence' in src, (
        "SequentialAnimation for the ticker is missing id: tickerScrollSequence"
    )


def test_ticker_restarts_on_text_change():
    """onTextChanged must call tickerScrollSequence.restart() so that a text
    update mid-animation does not leave the ticker running at the wrong speed."""
    src = _read_ui()
    assert 'onTextChanged: tickerScrollSequence.restart()' in src, (
        "Ticker Text element does not restart the animation when text changes."
    )


def test_ticker_duration_has_minimum():
    """Math.max guards against a degenerate zero-length text producing duration 0."""
    src = _read_ui()
    ticker_block_start = src.find('id: tickerScrollSequence')
    assert ticker_block_start != -1, "tickerScrollSequence animation not found"
    window = src[ticker_block_start:ticker_block_start + 600]
    assert 'Math.max(' in window, (
        "Ticker duration lacks a Math.max(...) guard; a very short text could "
        "produce a near-zero duration and cause a visual flash."
    )
