#!/usr/bin/env python3
"""
solve-hcaptcha-audio.py — Solve hCaptcha via audio challenge + Whisper ASR.

Usage:
    python3 scripts/solve-hcaptcha-audio.py [--no-click-audio] [--wait N]

Exits 0 and prints the transcription (e.g. "3 7 2 4 1 5") to stdout on success.
Exits 1 on failure (details logged to stderr).

Flow:
  1. Find Chrome CDP endpoint from running processes (--remote-debugging-port=N)
  2. Connect via Playwright connect_over_cdp()
  3. Traverse all frames to find the hCaptcha challenge iframe
  4. (Optionally) click the audio button to switch challenge mode
  5. Extract <audio> src (HTTP URL or blob)
  6. Download / decode audio to temp file
  7. Transcribe with Whisper base model
  8. Print cleaned digit string to stdout

NOTE: Does NOT close/kill the Chrome process — just reads state and disconnects.
"""

import sys
import os
import re
import subprocess
import tempfile
import time
import argparse
import base64

# ── CDP discovery ─────────────────────────────────────────────────────────────

def find_chrome_cdp_ports():
    """Return list of --remote-debugging-port values from running Chrome processes."""
    try:
        out = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.DEVNULL)
        ports = list(set(int(m) for m in re.findall(r"--remote-debugging-port=(\d+)", out)))
        return ports
    except Exception:
        return []


def get_ws_url(port, timeout=2):
    """Return the browser WebSocket debugger URL for a CDP port, or None."""
    try:
        import requests as req
        r = req.get(f"http://127.0.0.1:{port}/json/version", timeout=timeout)
        if r.ok:
            return r.json().get("webSocketDebuggerUrl")
    except Exception:
        pass
    return None


def find_hcaptcha_frame(playwright):
    """
    Scan all known Chrome CDP ports for a page with a live hCaptcha challenge
    iframe (URL contains 'hcaptcha.com' AND 'challenge').

    Returns (browser, frame) on success.
    Returns (None, None) if nothing found.

    IMPORTANT: Do NOT call browser.close() on the returned browser — it would
    kill the gateway's Chrome. Just let the script exit naturally.
    """
    ports = find_chrome_cdp_ports()
    # Fallback port range in case ps parsing missed any
    for fb in [9222, 9223, 9224, 18801, 18802, 18803, 18804, 18805]:
        if fb not in ports:
            ports.append(fb)

    for port in sorted(ports):
        ws_url = get_ws_url(port)
        if not ws_url:
            continue

        print(f"[cdp] trying port {port} ...", file=sys.stderr)
        try:
            browser = playwright.chromium.connect_over_cdp(ws_url, timeout=5000)
        except Exception as e:
            print(f"[cdp] port {port}: connect failed: {e}", file=sys.stderr)
            continue

        for ctx in browser.contexts:
            for page in ctx.pages:
                for frame in page.frames:
                    url = frame.url
                    if "hcaptcha.com" in url and "challenge" in url:
                        print(f"[cdp] port {port}: hCaptcha frame found: {url[:100]}", file=sys.stderr)
                        return browser, frame

        # No hCaptcha on this Chrome — leave it alone (don't close)
        print(f"[cdp] port {port}: no hCaptcha frame", file=sys.stderr)

    return None, None


# ── hCaptcha audio extraction ─────────────────────────────────────────────────

_JS_CLICK_AUDIO_BTN = """
() => {
    // Try common selectors for the audio challenge button
    const candidates = [
        'button.audio-button',
        'button[id*="audio"]',
        'button[class*="audio"]',
        '[aria-label*="audio" i]',
        '[aria-label*="sound" i]',
        '[title*="audio" i]',
        '[data-type="audio"]',
    ];
    for (const sel of candidates) {
        const el = document.querySelector(sel);
        if (el) { el.click(); return 'clicked:' + sel; }
    }
    // Last resort: any <button> whose label/text mentions audio or sound
    for (const btn of document.querySelectorAll('button')) {
        const lbl = (btn.getAttribute('aria-label') || btn.textContent || '').toLowerCase();
        if (lbl.includes('audio') || lbl.includes('sound')) {
            btn.click();
            return 'clicked:text-match';
        }
    }
    return 'not-found';
}
"""

_JS_GET_AUDIO_SRC = """
() => {
    const audio = document.querySelector('audio');
    if (!audio) return null;
    if (audio.src && !audio.src.startsWith('about:') && !audio.src.startsWith('data:')) {
        return audio.src;
    }
    const source = audio.querySelector('source');
    if (source && source.src) return source.src;
    return null;
}
"""

_JS_BLOB_TO_B64 = """
async (blobUrl) => {
    const resp = await fetch(blobUrl);
    const buf = await resp.arrayBuffer();
    const bytes = new Uint8Array(buf);
    // Build base64 in chunks to avoid call-stack overflow on large buffers
    let binary = '';
    const chunk = 8192;
    for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
}
"""


def extract_audio(frame, click_audio=True, wait_secs=2.5):
    """
    Extract audio data from the hCaptcha challenge frame.

    Returns:
        (tmp_path, True)   — path to downloaded audio file, always True on success
        (None, False)      — on failure
    """
    # 1. Check if audio element already present
    src = frame.evaluate(_JS_GET_AUDIO_SRC)

    if not src and click_audio:
        print("[captcha] no audio element yet — clicking audio button", file=sys.stderr)
        result = frame.evaluate(_JS_CLICK_AUDIO_BTN)
        print(f"[captcha] audio btn click: {result}", file=sys.stderr)
        time.sleep(wait_secs)
        src = frame.evaluate(_JS_GET_AUDIO_SRC)

    if not src:
        print("[captcha] audio src not found after click", file=sys.stderr)
        return None, False

    print(f"[captcha] audio src: {src[:120]}", file=sys.stderr)

    # 2. Save audio to temp file
    suffix = ".mp3"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    try:
        if src.startswith("blob:"):
            print("[captcha] blob URL — reading via JS fetch", file=sys.stderr)
            b64 = frame.evaluate(_JS_BLOB_TO_B64, src)
            with open(tmp_path, "wb") as f:
                f.write(base64.b64decode(b64))
        else:
            import requests as req
            print("[captcha] downloading HTTP audio", file=sys.stderr)
            r = req.get(src, timeout=30)
            r.raise_for_status()
            with open(tmp_path, "wb") as f:
                f.write(r.content)
    except Exception as e:
        print(f"[captcha] audio download failed: {e}", file=sys.stderr)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None, False

    size = os.path.getsize(tmp_path)
    print(f"[captcha] audio saved: {tmp_path} ({size} bytes)", file=sys.stderr)
    return tmp_path, True


# ── Whisper transcription ─────────────────────────────────────────────────────

def transcribe(audio_path):
    """
    Transcribe audio using Whisper base model.
    Returns cleaned digit string (e.g. "3 7 2 4 1 5"), or "" on failure.
    """
    try:
        import whisper
    except ImportError:
        print("[whisper] ERROR: openai-whisper not installed. Run: pip install openai-whisper", file=sys.stderr)
        return ""

    print("[whisper] loading base model ...", file=sys.stderr)
    model = whisper.load_model("base")
    print("[whisper] transcribing ...", file=sys.stderr)

    result = model.transcribe(audio_path, language="en", fp16=False)
    raw = result.get("text", "").strip()
    print(f"[whisper] raw transcript: {raw!r}", file=sys.stderr)

    # hCaptcha audio answers are digit sequences (e.g. "3 7 2 4 1 5")
    # Strip everything except digits and whitespace
    cleaned = re.sub(r"[^0-9\s]", "", raw).strip()
    cleaned = " ".join(cleaned.split())  # normalize whitespace
    return cleaned


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Solve hCaptcha audio challenge with Whisper")
    parser.add_argument(
        "--no-click-audio",
        dest="click_audio",
        action="store_false",
        default=True,
        help="Skip clicking the audio button (assume challenge already in audio mode)",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=2.5,
        help="Seconds to wait after clicking audio button (default: 2.5)",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright", file=sys.stderr)
        sys.exit(1)

    print("[solve] hCaptcha audio solver starting ...", file=sys.stderr)

    tmp_path = None
    try:
        with sync_playwright() as p:
            browser, frame = find_hcaptcha_frame(p)
            if frame is None:
                print(
                    "ERROR: No hCaptcha challenge iframe found in any running Chrome instance.\n"
                    "Make sure the hCaptcha is visible on the page and the browser is open.",
                    file=sys.stderr,
                )
                sys.exit(1)

            tmp_path, ok = extract_audio(frame, click_audio=args.click_audio, wait_secs=args.wait)
            # Let sync_playwright context exit naturally — do NOT call browser.close()
            # (that would kill the gateway's Chrome process)

        if not ok or not tmp_path:
            print("ERROR: Could not extract audio from hCaptcha", file=sys.stderr)
            sys.exit(1)

        answer = transcribe(tmp_path)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not answer:
        print("ERROR: Whisper returned empty result (no digits found in transcription)", file=sys.stderr)
        sys.exit(1)

    print(f"[solve] answer: {answer!r}", file=sys.stderr)
    print(answer)  # ← stdout: the answer for the subagent to use
    sys.exit(0)


if __name__ == "__main__":
    main()
