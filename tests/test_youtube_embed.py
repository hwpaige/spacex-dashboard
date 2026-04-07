"""Tests for youtube_embed.html to guard against the playlist memory-leak
regression caused by the loop=1 URL parameter.

When loop=1 is present in the YouTube embed URL, YouTube creates a brand-new
iframe / player instance on every cycle without destroying the previous one.
Over time this causes unbounded memory and CPU growth making the application
very slow.  The fix is to remove loop=1 and handle looping in JavaScript via
the YouTube IFrame Player API's onStateChange callback.
"""

import os
import re

EMBED_HTML_PATH = os.path.join(os.path.dirname(__file__), '..', 'src', 'youtube_embed.html')


def _read_embed_html():
    with open(EMBED_HTML_PATH, 'r', encoding='utf-8') as fh:
        return fh.read()


def _strip_html_comments(html):
    """Remove <!-- ... --> comment blocks so tests only inspect live code."""
    return re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)


def test_loop1_not_in_embed_url():
    """Ensure loop=1 is NOT present in the functional embed HTML (outside comments).

    Using loop=1 with enablejsapi=1 causes YouTube to allocate a new player
    instance on every loop cycle without cleaning up the old one, leading to a
    progressive memory / CPU leak.
    """
    html = _strip_html_comments(_read_embed_html())
    # The problematic parameter must be absent from live code
    assert 'loop=1' not in html, (
        "loop=1 was found in youtube_embed.html (outside of HTML comments). "
        "This causes YouTube to create a new player instance on every loop "
        "cycle (memory leak). Handle looping via the IFrame Player API instead."
    )


def test_iframe_api_used_for_looping():
    """Ensure the YouTube IFrame Player API is loaded and used for looping.

    The API script tag and onStateChange / playVideoAt pattern must be present
    so that the single player instance is reused when the playlist ends.
    """
    html = _read_embed_html()
    assert 'https://www.youtube.com/iframe_api' in html, (
        "https://www.youtube.com/iframe_api not found – the IFrame Player API must be "
        "loaded to handle looping without creating extra player instances."
    )
    assert 'onStateChange' in html, (
        "onStateChange handler not found – playlist looping must be driven "
        "by the IFrame Player API state change event, not the loop=1 param."
    )
    assert 'playVideoAt' in html, (
        "playVideoAt call not found – the ENDED state handler must call "
        "playVideoAt(0) to restart the playlist within the same player instance."
    )


def test_playlist_id_preserved():
    """Ensure the Starship playlist ID is still referenced in the embed."""
    html = _read_embed_html()
    assert 'PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY' in html, (
        "Starship playlist ID not found in youtube_embed.html."
    )


def test_autoplay_and_mute_present():
    """Autoplay and mute must still be enabled for the kiosk use-case."""
    html = _read_embed_html()
    assert 'autoplay' in html, "autoplay must be present in youtube_embed.html"
    assert 'mute' in html, "mute must be present in youtube_embed.html"


def test_quality_cap_on_ready():
    """setPlaybackQuality must be called in the onReady handler.

    Capping the playback quality at 'medium' (360p) prevents a single
    high-resolution video from pre-buffering hundreds of megabytes and
    exhausting RAM on memory-constrained hardware such as Raspberry Pi.
    The cap must be applied before playVideo() so the player never selects
    a higher-bitrate stream.
    """
    html = _strip_html_comments(_read_embed_html())
    assert 'setPlaybackQuality' in html, (
        "setPlaybackQuality not found in youtube_embed.html – quality must be "
        "capped to limit video buffer memory usage."
    )
    assert 'QUALITY_CAP' in html, (
        "QUALITY_CAP variable not found – quality cap must be defined as a "
        "named constant so it is easy to tune."
    )


def test_quality_cap_on_state_change():
    """setPlaybackQuality must also be called whenever a new video starts playing.

    Each playlist item gets its own buffer allocation.  Re-applying the quality
    cap in the PLAYING state handler ensures every video in the playlist is
    subject to the same limit, not just the first one.
    """
    html = _strip_html_comments(_read_embed_html())
    # Both the PLAYING state check and the quality-cap call must be present.
    assert 'YT.PlayerState.PLAYING' in html, (
        "YT.PlayerState.PLAYING check not found in onStateChange – the quality "
        "cap must be re-applied each time a new video begins to play."
    )
    assert 'setPlaybackQuality' in html, (
        "setPlaybackQuality not found in youtube_embed.html (outside comments)."
    )
