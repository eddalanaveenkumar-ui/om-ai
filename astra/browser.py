import re
import time
import webbrowser
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from html.parser import HTMLParser

# Common spoken website names. Extend this map as needed.
SITE_ALIASES = {
    "youtube": "https://www.youtube.com",
    "you tube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "nvidia": "https://www.nvidia.com",
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "github": "https://github.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://openai.com",
    "x": "https://x.com",
    "twitter": "https://x.com",
    "linkedin": "https://www.linkedin.com",
    "stackoverflow": "https://stackoverflow.com",
}

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.parts.append(data)

def extract_url(text: str) -> str:
    """Resolve explicit URLs, bare domains, or common natural-language site names."""
    original = (text or "").strip()
    if not original:
        raise ValueError("Please tell Astra which website to open.")

    # Prefer an explicit URL anywhere in the instruction.
    match = re.search(r"https?://[^\s<>'\"\\)]+", original, flags=re.IGNORECASE)
    if match:
        candidate = match.group(0).rstrip(".,;!?")
    else:
        # Handle bare domains such as youtube.com or www.example.org.
        domain_match = re.search(
            r"(?<![@\w.-])(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/[^\s<>'\"]*)?",
            original
        )
        if domain_match:
            candidate = "https://" + domain_match.group(0).rstrip(".,;!?")
        else:
            # Remove common command phrases and resolve a known website name.
            normalized = original.lower()
            normalized = re.sub(r"\b(open|launch|go to|navigate to|browse to|visit|website|web site|browser|and then|then|please)\b", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip(" .,!?:;")
            candidate = SITE_ALIASES.get(normalized)
            if not candidate:
                # Match a known site name embedded in a longer phrase.
                for name, url in sorted(SITE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
                    if re.search(rf"\b{re.escape(name)}\b", normalized):
                        candidate = url
                        break
            if not candidate:
                raise ValueError(
                    "I couldn't identify the website. Try a website name such as "
                    "'Open YouTube', or provide its domain, such as 'youtube.com'."
                )

    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Only valid HTTP and HTTPS website addresses are allowed.")
    return candidate

def open_and_check(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Blocked unsafe or invalid URL.")

    opened = webbrowser.open_new_tab(url)
    time.sleep(2.0)

    result = {
        "action": "open_browser_url",
        "url": url,
        "browser_open_requested": bool(opened),
        "http_check": "not_checked",
        "http_status": None,
        "page_title": None,
        "verified": False,
        "notes": []
    }

    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 AstraComputerAgent/1.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read(1_500_000)
            result["http_status"] = response.status
            result["http_check"] = "reachable"
            parser = TitleParser()
            try:
                parser.feed(body.decode(response.headers.get_content_charset() or "utf-8", errors="replace"))
                result["page_title"] = " ".join(" ".join(parser.parts).split()) or None
            except Exception:
                result["notes"].append("Could not parse the page title.")
            result["verified"] = 200 <= response.status < 400
    except Exception as exc:
        result["http_check"] = "failed"
        result["notes"].append(
            "The browser open was requested, but HTTP verification failed: " + str(exc)
        )

    if not opened:
        result["notes"].append(
            "The system browser did not confirm the open request; check the default browser configuration."
        )
    return result



def extract_youtube_search_query(task: str) -> str:
    """Extract the song the user actually requested; never substitute a demo track."""
    text = (task or "").strip()
    # Quoted song/artist names are the least ambiguous form.
    quoted = re.search(r"[\"'“”‘’]([^\"'“”‘’]{2,100})[\"'“”‘’]", text)
    if quoted:
        candidate = quoted.group(1).strip()
        if candidate and not re.match(r"^https?://", candidate, re.I):
            return candidate

    patterns = [
        r"\b(?:play|search(?:\s+youtube)?\s+for|find)\s+(?:the\s+)?(?:song\s+)?(.+?)\s+(?:song|music\s+video)\b",
        r"\b(?:play|search(?:\s+youtube)?\s+for|find)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            candidate = match.group(1).strip(" .,:;!?\"'“”‘’")
            candidate = re.sub(r"^(?:the\s+)?(?:song|music)\s+", "", candidate, flags=re.I)
            candidate = re.sub(r"\s+(?:on\s+)?youtube$", "", candidate, flags=re.I).strip()
            if candidate and candidate.lower() not in {"a", "a song", "song", "music", "a music"}:
                return candidate
    # Generic requests may choose a neutral popular-music search, but never a named demo song.
    if re.search(r"\b(play|song|music)\b", text, re.I):
        return "popular songs"
    raise ValueError("No song title was found in the request.")

def play_youtube_song(chrome_executable: str, search_query: str) -> dict:
    """Open a visible Chrome window, search YouTube, and play a result via DOM automation."""
    from pathlib import Path
    import os
    import subprocess
    from playwright.sync_api import sync_playwright

    if not chrome_executable or not Path(chrome_executable).is_file():
        raise FileNotFoundError("Google Chrome executable was not found.")
    profile_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "AstraChromeProfile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = 9222
    chrome_process = subprocess.Popen([
        chrome_executable,
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={port}",
        "--no-first-run", "--no-default-browser-check", "--start-maximized",
        "https://www.youtube.com/results?search_query=" + __import__("urllib.parse").parse.quote(search_query),
    ], close_fds=True)
    result = {
        "action": "youtube_search_and_play", "browser": "Google Chrome",
        "search_query": search_query, "profile_directory": str(profile_dir),
        "chrome_pid": chrome_process.pid, "youtube_url": None, "video_title": None,
        "playback_started": False, "verification": "pending", "notes": [],
    }
    pw = sync_playwright().start()
    browser = None
    try:
        # Wait for Chrome's local DevTools endpoint without using screen coordinates.
        deadline = time.time() + 25
        last_error = None
        while time.time() < deadline:
            try:
                browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=2000)
                break
            except Exception as exc:
                last_error = exc
                time.sleep(0.5)
        if browser is None:
            raise RuntimeError(f"Could not connect to the launched Chrome window: {last_error}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.youtube.com/results?search_query=" + __import__("urllib.parse").parse.quote(search_query), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        # Consent handling is limited to YouTube's basic cookie prompt.
        for label in ("Accept all", "Reject all", "I agree"):
            try:
                button = page.get_by_role("button", name=label, exact=True)
                if button.count() and button.first.is_visible(timeout=800):
                    button.first.click(timeout=1500)
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass
        videos = page.locator("ytd-video-renderer a#video-title")
        videos.first.wait_for(state="visible", timeout=30000)
        chosen = None
        for idx in range(min(videos.count(), 8)):
            candidate = videos.nth(idx)
            href = candidate.get_attribute("href") or ""
            title = (candidate.get_attribute("title") or candidate.inner_text() or "").strip()
            if "/watch?v=" in href and title:
                chosen = (candidate, title)
                break
        if not chosen:
            raise RuntimeError("YouTube search loaded, but no playable video result was found.")
        link, title = chosen
        link.click()
        page.wait_for_url("**/watch?**", timeout=30000)
        page.wait_for_timeout(2500)
        video = page.locator("video").first
        video.wait_for(state="attached", timeout=20000)
        try:
            video.evaluate("v => v.play().catch(() => {})")
        except Exception:
            pass
        page.wait_for_timeout(1800)
        state = video.evaluate("v => ({paused: v.paused, currentTime: v.currentTime, readyState: v.readyState})")
        title_tokens = {t for t in re.findall(r"[a-z0-9]+", search_query.lower()) if len(t) > 2}
        result_tokens = {t for t in re.findall(r"[a-z0-9]+", title.lower()) if len(t) > 2}
        title_match = (not title_tokens) or bool(title_tokens & result_tokens)
        playback_active = bool(not state.get("paused") and state.get("currentTime", 0) > 1.0 and state.get("readyState", 0) >= 2)
        result.update({
            "youtube_url": page.url, "video_title": title,
            "requested_song_match": title_match,
            "playback_started": playback_active and title_match,
            "video_state": state,
            "verification": ("requested song appears to be playing" if playback_active and title_match else
                             "video is playing but title does not clearly match the requested song" if playback_active else
                             "video opened; browser may require one manual Play click"),
        })
        if not title_match:
            result["notes"].append("The selected video title does not clearly match the requested song. Playback is not reported as successful.")
        if state.get("paused"):
            result["notes"].append("Chrome opened the video, but autoplay policy may require a manual Play click.")
        return result
    finally:
        # Disconnect Playwright without closing the user-visible Chrome window.
        try:
            pw.stop()
        except Exception:
            pass
