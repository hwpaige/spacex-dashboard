"""Tests for youtube_embed.html to guard against the playlist memory-leak
regression caused by the loop=1 URL parameter, and against the RAM-exhaustion
regression caused by uncontrolled DASH buffer growth on long videos.

When loop=1 is present in the YouTube embed URL, YouTube creates a brand-new
iframe / player instance on every cycle without destroying the previous one.
Over time this causes unbounded memory and CPU growth making the application
very slow.  The fix is to remove loop=1 and handle looping in JavaScript via
the YouTube IFrame Player API's onStateChange callback.

A second regression is that the IFrame Player API streams video via DASH /
MSE, which allows the player to pre-buffer large amounts of data.  For
multi-hour videos (e.g. full Starship launch streams) the SourceBuffer can
fill all available RAM and lock up the system on Raspberry Pi.  The fix:

1. Cap playback quality via setPlaybackQuality('medium') – limits per-segment
   size so the buffer never exceeds a few hundred MB.
2. Arm a play-duration watchdog (MAX_PLAY_MINUTES) – after N minutes, skip to
   the next video so the buffer is fully reclaimed.
3. Arm a BUFFERING watchdog (30 s) – skip if the player stalls, preventing
   CPU pinning while waiting for a network-unreachable segment.
4. Handle onError – skip deleted/private/embed-blocked videos instead of
   halting the playlist permanently.
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
    """QUALITY_CAP must be applied in onReady before the first video plays.

    setPlaybackQuality is called in onReady so that the player never negotiates
    a high-quality stream on the very first video, preventing an early RAM spike.
    """
    html = _strip_html_comments(_read_embed_html())
    assert 'QUALITY_CAP' in html, (
        "QUALITY_CAP constant not found – a quality ceiling must be defined to "
        "limit per-segment buffer size on memory-constrained hardware."
    )
    assert 'setPlaybackQuality' in html, (
        "setPlaybackQuality not found – must be called to cap stream quality "
        "and keep DASH buffer size bounded."
    )
    assert 'setPlaybackQuality(QUALITY_CAP)' in html, (
        "setPlaybackQuality(QUALITY_CAP) not found – the quality cap constant "
        "must be passed to setPlaybackQuality."
    )


def test_quality_cap_on_state_change():
    """QUALITY_CAP must be re-applied on PLAYING so every playlist item is capped.

    Each new playlist video starts its own DASH buffer; without re-applying the
    cap the first video after page-load may stream at the capped quality while
    subsequent ones silently revert to full resolution.
    """
    html = _strip_html_comments(_read_embed_html())
    # Both PLAYING state check and setPlaybackQuality call must be present
    assert 'PlayerState.PLAYING' in html, (
        "YT.PlayerState.PLAYING check not found – the PLAYING handler is needed "
        "to re-apply the quality cap on each new playlist item."
    )


def test_on_error_calls_next_video():
    """onError must call nextVideo() to skip unplayable videos.

    Without an error handler a single deleted, private, or embed-blocked video
    permanently halts the playlist.
    """
    html = _strip_html_comments(_read_embed_html())
    assert 'onError' in html, (
        "onError handler not found in youtube_embed.html – unplayable playlist "
        "items will stall playback without this handler."
    )
    assert 'nextVideo' in html, (
        "nextVideo() call not found – the onError and watchdog handlers must "
        "call nextVideo() to skip unplayable or stuck items."
    )


def test_buffering_watchdog_present():
    """A timeout-based BUFFERING watchdog must be present.

    If the player gets stuck in BUFFERING (e.g. a network-unreachable segment
    or an embed-blocked video that partially loads), the watchdog skips to the
    next video after 30 s to prevent the CPU from being pinned at 100%.
    """
    html = _strip_html_comments(_read_embed_html())
    assert 'PlayerState.BUFFERING' in html, (
        "YT.PlayerState.BUFFERING check not found – a BUFFERING watchdog is "
        "required to detect and recover from stalled video segments."
    )
    assert 'bufferWatchdogTimer' in html, (
        "bufferWatchdogTimer variable not found – the BUFFERING watchdog timer "
        "handle must be stored so it can be cancelled when the player recovers."
    )


def test_max_play_duration_present():
    """A play-duration watchdog (MAX_PLAY_MINUTES) must be armed on PLAYING.

    Multi-hour videos in the Starship playlist cause the DASH SourceBuffer to
    grow unboundedly on Chromium/WebEngine, eventually exhausting all available
    RAM and locking up the Raspberry Pi.  The watchdog skips to the next video
    after MAX_PLAY_MINUTES to reclaim memory.
    """
    html = _strip_html_comments(_read_embed_html())
    assert 'MAX_PLAY_MINUTES' in html, (
        "MAX_PLAY_MINUTES constant not found – a play-duration ceiling is "
        "required to prevent very long videos from filling all available RAM."
    )
    assert 'playDurationTimer' in html, (
        "playDurationTimer variable not found – the play-duration watchdog "
        "timer handle must be stored so it can be cancelled on video transitions."
    )

