"""Tests that validate the globe-freezing regression fixes in src/globe.html.

Each test is focused on one specific root-cause fix so failures are easy to
diagnose.  The tests parse the HTML/GLSL as text rather than executing it so
they run without a browser or GPU.
"""

import re
from pathlib import Path

GLOBE_HTML_PATH = Path(__file__).parent.parent / 'src' / 'globe.html'


def _read_globe():
    return GLOBE_HTML_PATH.read_text(encoding='utf-8')


def _extract_function_body(html: str, function_name: str) -> str:
    """Return the complete source text of the named JS function (including braces).

    Uses brace-depth tracking so it works regardless of how long the body is.
    Returns an empty string if the function is not found.
    """
    start = html.find(f'function {function_name}()')
    if start == -1:
        return ''
    depth = 0
    end = start
    entered = False
    for i, ch in enumerate(html[start:], start=start):
        if ch == '{':
            depth += 1
            entered = True
        elif ch == '}':
            depth -= 1
            if entered and depth == 0:
                end = i
                break
    return html[start:end + 1]


def _extract_iife_after(html: str, marker: str, max_chars: int = 5000) -> str:
    """Return the text of the first IIFE ((function(){ ... })()) after *marker*.

    Uses brace-depth tracking up to *max_chars* characters after the marker.
    """
    pos = html.find(marker)
    if pos == -1:
        return ''
    section = html[pos:pos + max_chars]
    # Find the opening paren of the IIFE
    iife_start = section.find('(function ()')
    if iife_start == -1:
        iife_start = section.find('(function()')
    if iife_start == -1:
        return section  # fallback: return the raw section
    depth = 0
    entered = False
    end = iife_start
    for i, ch in enumerate(section[iife_start:], start=iife_start):
        if ch == '{':
            depth += 1
            entered = True
        elif ch == '}':
            depth -= 1
            if entered and depth == 0:
                end = i
                break
    return section[iife_start:end + 1]


# ---------------------------------------------------------------------------
# Fix 1 – GLSL variable `n3` must not be re-declared in an inner scope
# ---------------------------------------------------------------------------

def test_glsl_no_n3_redeclaration():
    """The cloud fragment shader must not redeclare 'float n3' inside the
    hasTexture branch.  A duplicate declaration in an inner scope is illegal
    in GLSL ES 1.00 (WebGL 1) and causes shader compile failure on strict
    drivers (e.g. Raspberry Pi / VideoCore) making clouds appear frozen.
    """
    html = _read_globe()
    # Extract the fragment shader source from between the back-tick literals.
    frag_match = re.search(
        r'const cloudFragmentShader\s*=\s*`(.*?)`\s*;',
        html,
        re.DOTALL,
    )
    assert frag_match, "cloudFragmentShader template literal not found"
    shader = frag_match.group(1)

    declarations = re.findall(r'\bfloat\s+n3\b', shader)
    assert len(declarations) <= 1, (
        f"'float n3' declared {len(declarations)} times in cloudFragmentShader. "
        "A redeclaration inside an inner scope is illegal in GLSL ES 1.00 and "
        "causes shader compile failure on strict GLES drivers (Pi VideoCore). "
        "Rename the inner variable (e.g. n3b) to fix this."
    )


# ---------------------------------------------------------------------------
# Fix 2 – clouds object must be cached, not traversed every frame
# ---------------------------------------------------------------------------

def test_clouds_object_cached():
    """The clouds mesh should be cached in a module-level variable (cloudsObject)
    and used in animate() rather than calling scene.getObjectByName() on every
    frame.  The O(n) scene traversal on every frame is a needless CPU cost on Pi
    and grows as trajectory objects are added to the scene.
    """
    html = _read_globe()
    assert 'cloudsObject' in html, (
        "'cloudsObject' variable not found in globe.html. "
        "The clouds mesh should be cached at creation time to avoid repeated "
        "O(n) scene.getObjectByName() calls in the animation loop."
    )


def test_get_object_by_name_not_in_animate():
    """scene.getObjectByName('clouds') must not appear inside the animate()
    function body.  The animate loop runs at 30–60 fps; calling getObjectByName
    there performs a full scene-tree traversal on every frame.
    """
    html = _read_globe()
    animate_body = _extract_function_body(html, 'animate')
    assert animate_body, "function animate() not found"
    assert "getObjectByName" not in animate_body, (
        "scene.getObjectByName() call found inside animate(). "
        "Cache the clouds mesh at init time and use the cached reference instead."
    )


# ---------------------------------------------------------------------------
# Fix 3 – cloud rotation must use incremental delta-time, not absolute time
# ---------------------------------------------------------------------------

def test_cloud_rotation_uses_delta_not_absolute():
    """Cloud rotation must be driven by a cumulative delta-time accumulator
    (cloudsRotY) rather than 'absoluteTime * <constant>'.

    Using absolute time means clouds.rotation.y is SET to a new absolute value
    every frame.  When absoluteTime wraps at 3600 s the cloud layer snaps to
    a completely different position in a single frame – visually indistinguishable
    from a freeze and then a jarring jump.
    """
    html = _read_globe()
    animate_body = _extract_function_body(html, 'animate')
    assert animate_body, "function animate() not found"

    # The old absolute-time pattern must be gone
    old_pattern = re.search(r'clouds\.rotation\.y\s*=\s*absoluteTime', animate_body)
    assert old_pattern is None, (
        "clouds.rotation.y is still assigned using absoluteTime inside animate(). "
        "Use an incremental cloudsRotY accumulator (cloudsRotY += dtSec * speed) "
        "to prevent the cloud layer from jumping when absoluteTime wraps."
    )

    # The new accumulator must be present
    assert 'cloudsRotY' in html, (
        "'cloudsRotY' accumulator not found in globe.html. "
        "Cloud rotation must accumulate delta increments to stay smooth across wraps."
    )


# ---------------------------------------------------------------------------
# Fix 4 – watchdog must detect a stopped RAF loop and restart it
# ---------------------------------------------------------------------------

def test_watchdog_has_call_counter():
    """The self-healing watchdog must track the animate() call counter
    (__animateCalls) to detect when the RAF loop itself has stopped, not just
    when rendering has stalled.  Without this, a Qt WebEngine view becoming
    non-visible (which pauses RAF) can freeze the globe permanently.
    """
    html = _read_globe()
    assert '__animateCalls' in html, (
        "'__animateCalls' not found.  The watchdog needs a call counter to detect "
        "when the RAF loop has stopped, not just when rendering has stalled."
    )
    assert '__animateStarted' in html, (
        "'__animateStarted' guard not found.  Without it the watchdog would try to "
        "restart animate() before THREE.js has finished initialising."
    )


def test_watchdog_restarts_raf():
    """The watchdog must call requestAnimationFrame(animate) when the RAF loop
    appears to have stopped (call counter unchanged for one watchdog tick).
    Previously it only called resumeSpin() which only resets JS flags but does
    not restart a stopped RAF loop.
    """
    html = _read_globe()
    watchdog_body = _extract_iife_after(html, 'Self-healing watchdog')
    assert watchdog_body, "'Self-healing watchdog' IIFE not found"
    assert 'requestAnimationFrame(animate)' in watchdog_body, (
        "The self-healing watchdog does not call requestAnimationFrame(animate) to "
        "restart a stopped RAF loop.  resumeSpin() alone only resets JS state flags "
        "and cannot restart a loop that Qt WebEngine has throttled or paused."
    )


# ---------------------------------------------------------------------------
# Fix 5 – __lastRenderTs updated only inside successful render block
# ---------------------------------------------------------------------------

def test_last_render_ts_inside_render_block():
    """__lastRenderTs must only be updated when renderer.render() actually
    succeeds (inside the try block), not unconditionally after the render
    conditional.  Moving it outside means the watchdog cannot detect scenarios
    where the renderer exists but produces no output (e.g. after WebGL context
    loss where Three.js render() is a silent no-op).
    """
    html = _read_globe()
    animate_body = _extract_function_body(html, 'animate')
    assert animate_body, "function animate() not found"

    render_pos = animate_body.find('renderer.render(scene, camera)')
    ts_pos = animate_body.find('__lastRenderTs = now')
    assert render_pos != -1, "renderer.render() not found inside animate()"
    assert ts_pos != -1, "__lastRenderTs = now not found inside animate()"
    assert ts_pos > render_pos, (
        "__lastRenderTs = now appears BEFORE renderer.render() in animate(). "
        "It must only be set after a successful render so the watchdog can detect "
        "frames where the renderer fails silently."
    )


# ---------------------------------------------------------------------------
# Fix 6 – WebGL context restore marks texture uniforms for re-upload
# ---------------------------------------------------------------------------

def test_context_restored_marks_texture_uniforms():
    """The webglcontextrestored handler must mark texture uniforms needsUpdate
    so that GPU-side textures (including the cloud shader sampler) are fully
    re-uploaded after a context restore.  Without this, clouds stay blank or
    render black after a GPU memory pressure event on Pi.
    """
    html = _read_globe()
    restored_start = html.find("webglcontextrestored")
    assert restored_start != -1, "webglcontextrestored handler not found"
    # Extract the full handler body using brace-depth tracking
    depth = 0
    entered = False
    end = restored_start
    for i, ch in enumerate(html[restored_start:], start=restored_start):
        if ch == '{':
            depth += 1
            entered = True
        elif ch == '}':
            depth -= 1
            if entered and depth == 0:
                end = i
                break
    restored_body = html[restored_start:end + 1]
    assert 'isTexture' in restored_body or 'needsUpdate' in restored_body, (
        "The webglcontextrestored handler does not appear to mark textures for "
        "re-upload.  After a WebGL context restore all GPU textures are lost and "
        "must be re-uploaded via texture.needsUpdate = true."
    )
    assert 'uniforms' in restored_body, (
        "The webglcontextrestored handler does not iterate over shader uniforms. "
        "Texture uniforms (e.g. cloudTexture) must also be marked needsUpdate."
    )


# ---------------------------------------------------------------------------
# Fix 7 – Watchdog must not accumulate duplicate RAF loops (globe disappearance)
# ---------------------------------------------------------------------------

def test_raf_handle_stored():
    """animate() must store the return value of requestAnimationFrame so the
    watchdog can cancel the pending callback before issuing a new one.

    Without storing the handle, when the watchdog fires Signal 2 (stalled RAF
    call counter) it issues an extra requestAnimationFrame(animate) even though
    the original loop is just temporarily throttled.  When the throttle lifts,
    both chains run in parallel, each scheduling another RAF, leading to
    exponential loop accumulation.  On a Pi running overnight this grows until
    the GPU/CPU is overwhelmed and the globe disappears entirely.
    """
    html = _read_globe()
    animate_body = _extract_function_body(html, 'animate')
    assert animate_body, "function animate() not found"
    assert '__rafId = requestAnimationFrame(animate)' in animate_body, (
        "animate() does not store the RAF handle (__rafId = requestAnimationFrame(animate)). "
        "The handle must be stored so the watchdog can cancel the pending callback "
        "before restarting the loop, preventing duplicate RAF chain accumulation."
    )


def test_watchdog_cancels_raf_before_restart():
    """The watchdog Signal 2 block must cancel any pending RAF callback via
    cancelAnimationFrame(__rafId) before issuing a fresh requestAnimationFrame.

    This prevents duplicate animate() chains from accumulating when Qt WebEngine
    temporarily throttles RAF (without fully stopping it).  Each un-cancelled
    restart creates a parallel loop, and after hours the exponential growth of
    concurrent loops overwhelms the Pi and causes the globe to disappear.
    """
    html = _read_globe()
    watchdog_body = _extract_iife_after(html, 'Self-healing watchdog')
    assert watchdog_body, "'Self-healing watchdog' IIFE not found"
    assert 'cancelAnimationFrame' in watchdog_body, (
        "The watchdog does not call cancelAnimationFrame before restarting the RAF "
        "loop.  Without cancelling the existing pending callback, every watchdog "
        "trigger during a throttle period adds another parallel animate() chain."
    )
    assert '__rafId' in watchdog_body, (
        "The watchdog does not reference __rafId.  It must cancel the current "
        "pending RAF handle before issuing a new requestAnimationFrame(animate) "
        "to guarantee exactly one animate() chain is ever active."
    )


# ---------------------------------------------------------------------------
# Fix 8 – Cloud fragment shader must use highp float to prevent cloud freeze
# ---------------------------------------------------------------------------

def test_cloud_fragment_shader_uses_highp():
    """The cloud fragment shader must declare 'precision highp float' (not
    mediump).

    On Raspberry Pi (VideoCore VI / Mali-class GPUs) mediump float is
    implemented as IEEE 754 half-precision (float16, 10-bit mantissa).  The
    cloud shader uses a 'time' uniform that grows from 0 to 3600 each hour.
    When absoluteTime exceeds ~1024, the per-frame delta (≈0.017 s at 60 fps)
    is smaller than the float16 ULP at that magnitude (~2 units), so the
    value the shader sees never changes and cloud animation appears completely
    frozen.

    Switching the fragment shader to 'precision highp float' (float32) keeps
    the ULP far below the per-frame delta for the full [0, 3600] range.
    """
    html = _read_globe()
    frag_match = re.search(
        r'const cloudFragmentShader\s*=\s*`(.*?)`\s*;',
        html,
        re.DOTALL,
    )
    assert frag_match, "cloudFragmentShader template literal not found"
    shader = frag_match.group(1)

    assert 'precision highp float' in shader, (
        "cloudFragmentShader uses 'precision mediump float' (or no precision "
        "declaration).  On Raspberry Pi, mediump = float16.  When the 'time' "
        "uniform exceeds ~1024 the per-frame delta falls below the float16 ULP "
        "and cloud animation freezes permanently until the wrap resets to 0. "
        "Change the fragment shader to 'precision highp float'."
    )
    assert 'precision mediump float' not in shader, (
        "cloudFragmentShader still contains 'precision mediump float'.  Remove "
        "or replace it with 'precision highp float' to prevent cloud animation "
        "from freezing on Raspberry Pi after ~17 minutes of uptime per hour."
    )


# ---------------------------------------------------------------------------
# Fix 9 – Inactivity fallback must also clear stuck activePointers > 0
# ---------------------------------------------------------------------------

def test_inactivity_fallback_handles_stuck_active_pointers():
    """The inactivity setInterval must reset activePointers when it has been
    stuck > 0 without any pointer movement for an extended period.

    On Qt/Raspberry Pi a non-mouse pointerdown can fire without a matching
    pointerup (e.g. the touch is released outside the Qt WebEngine window).
    This leaves activePointers > 0 indefinitely.  The existing inactivity
    guard checks 'activePointers === 0' as a precondition, so it never fires,
    leaving userInteracting = true stuck.  With userInteracting stuck true
    the auto-rotation branch is skipped every frame and the globe appears
    frozen after overnight use.

    The fix is to also reset activePointers (via clearInteraction) when it
    has been > 0 with no movement for a long time (e.g. 10 seconds).
    """
    html = _read_globe()
    # Find the inactivity setInterval block
    inactivity_start = html.find('Inactivity fallback')
    assert inactivity_start != -1, "'Inactivity fallback' comment not found"
    # Grab a reasonable window after the comment (the setInterval body)
    section = html[inactivity_start:inactivity_start + 2000]

    assert 'activePointers > 0' in section, (
        "The inactivity fallback setInterval does not check 'activePointers > 0'. "
        "A missed pointerup on Qt/Pi leaves activePointers stuck at a positive "
        "value, preventing clearInteraction() from being called and leaving "
        "userInteracting = true permanently frozen."
    )
    # The section must also call clearInteraction() in that path
    assert 'clearInteraction' in section, (
        "The inactivity fallback does not call clearInteraction() to reset the "
        "stuck activePointers state."
    )


# ---------------------------------------------------------------------------
# Fix 10 – webglcontextlost must invalidate __lastRenderTs immediately
# ---------------------------------------------------------------------------

def test_context_lost_handler_invalidates_render_timestamp():
    """The webglcontextlost handler must reset __lastRenderTs to 0 so the
    watchdog's Signal 1 fires on its very next tick after context loss.

    Three.js r128 silently returns from renderer.render() when the context is
    lost (_isContextLost = true) — no exception is raised, so the try/catch in
    animate() does not help.  Without __lastRenderTs = 0, the watchdog only
    discovers the stall after STALL_MS (3 s) from the *last successful render*
    before the context was lost, which could be up to 3 seconds later, leaving
    the globe frozen undetected.  Setting __lastRenderTs = 0 guarantees that
    now - __lastRenderTs >> STALL_MS immediately, so clearInteraction() and
    resumeSpin() are called on the very next watchdog tick.
    """
    html = _read_globe()
    lost_start = html.find('webglcontextlost')
    assert lost_start != -1, 'webglcontextlost handler not found'
    # Extract the complete handler body via brace-depth tracking
    depth = 0
    entered = False
    end = lost_start
    for i, ch in enumerate(html[lost_start:], start=lost_start):
        if ch == '{':
            depth += 1
            entered = True
        elif ch == '}':
            depth -= 1
            if entered and depth == 0:
                end = i
                break
    lost_body = html[lost_start:end + 1]
    assert '__lastRenderTs' in lost_body, (
        "The webglcontextlost handler does not reset __lastRenderTs. "
        "Three.js r128 returns silently from render() on context loss so the "
        "animate() render block still executes __lastRenderTs = now, hiding the "
        "freeze from the watchdog.  Add '__lastRenderTs = 0;' in the handler to "
        "force Signal 1 to fire immediately after context loss."
    )


# ---------------------------------------------------------------------------
# Fix 11 – __lastRenderTs must be gated on isContextLost() in animate()
# ---------------------------------------------------------------------------

def test_render_timestamp_guards_against_context_loss():
    """animate() must check renderer.getContext().isContextLost() and only
    update __lastRenderTs when the context is healthy.

    Three.js r128 sets an internal _isContextLost flag and returns early from
    renderer.render() when the WebGL context is lost — without throwing.  If
    __lastRenderTs is updated unconditionally after the (silent no-op) render,
    the watchdog's Signal 1 (render-timestamp stall) never fires, leaving the
    globe frozen indefinitely.  After the WebGL context is restored Three.js
    resets _isContextLost = false and rendering resumes, but only if the
    watchdog (or the webglcontextrestored handler) has had a chance to run.

    The fix: wrap the __lastRenderTs update in
        const _ctx = renderer.getContext();
        if (_ctx && !_ctx.isContextLost()) { __lastRenderTs = now; }
    so the watchdog correctly detects the stall during context loss.
    """
    html = _read_globe()
    animate_body = _extract_function_body(html, 'animate')
    assert animate_body, "function animate() not found"

    assert 'isContextLost()' in animate_body, (
        "animate() does not call isContextLost(). "
        "Three.js r128 silently no-ops renderer.render() on context loss.  "
        "Without the isContextLost() guard the watchdog never detects the stall "
        "and the globe stays frozen indefinitely after a GPU memory-pressure event."
    )
    # The isContextLost check must appear before __lastRenderTs = now
    ctx_lost_pos = animate_body.find('isContextLost()')
    ts_pos = animate_body.find('__lastRenderTs = now')
    assert ctx_lost_pos != -1 and ts_pos != -1, (
        "Either isContextLost() check or __lastRenderTs = now missing in animate()"
    )
    assert ctx_lost_pos < ts_pos, (
        "isContextLost() check must appear before __lastRenderTs = now in animate() "
        "so that __lastRenderTs is only updated when the context is not lost."
    )
