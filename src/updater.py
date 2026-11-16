"""In-app updates from GitHub Releases.

Flow: check ``releases/latest`` → download its ``MoneyTalks.dmg`` in the
background → copy the new ``MoneyTalks.app`` out of the disk image into
``~/Library/Application Support/MoneyTalks/updates`` and verify its signature.
The staged app replaces the running one when MoneyTalks quits, or straight away
(with a relaunch) when the user clicks "Restart to update".

The swap is done by a small shell script started just before the app exits: it
waits for the app's process to end, moves the old bundle aside, copies the new
one in, and puts the old one back if anything fails.
"""

import json
import os
import plistlib
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import certifi

from config import APP_SUPPORT_DIR

REPO = "nikhil-kunapareddy/moneytalks"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "MoneyTalks.dmg"
USER_AGENT = "MoneyTalks-Updater"
UPDATES_DIR = APP_SUPPORT_DIR / "updates"
CHECK_EVERY_SECONDS = 6 * 60 * 60
FIRST_CHECK_DELAY_SECONDS = 5

_INSTALL_SCRIPT = r"""#!/bin/sh
# MoneyTalks updater: wait for the app to quit, swap in the new bundle.
pid="$1"; new="$2"; target="$3"; relaunch="$4"
while kill -0 "$pid" 2>/dev/null; do sleep 0.3; done
backup="$target.previous"
rm -rf "$backup"
if mv "$target" "$backup"; then
  if ditto "$new" "$target"; then
    rm -rf "$backup" "$(dirname "$new")"
  else
    rm -rf "$target"; mv "$backup" "$target"   # put the old app back
  fi
fi
if [ "$relaunch" = "1" ]; then open "$target"; fi
rm -f "$0"
"""


class UpdateError(Exception):
    pass


@dataclass
class Release:
    version: str  # "0.2.5"
    page_url: str
    asset_url: str
    size: int


# ---------------------------------------------------------------------------
# Version and install location
# ---------------------------------------------------------------------------

def app_bundle() -> Optional[Path]:
    """The running MoneyTalks.app, or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    bundle = Path(sys.executable).resolve().parents[2]  # .app/Contents/MacOS/MoneyTalks
    return bundle if bundle.suffix == ".app" else None


def current_version() -> str:
    bundle = app_bundle()
    if bundle is None:
        return "0.0.0-dev"
    with open(bundle / "Contents" / "Info.plist", "rb") as f:
        return plistlib.load(f).get("CFBundleShortVersionString", "0.0.0")


def version_key(version: str) -> tuple[int, ...]:
    """'v0.2.4' → (0, 2, 4); '0.2.0-local' → (0, 2, 0)."""
    numbers = re.findall(r"\d+", version.split("-")[0])
    return tuple(int(n) for n in numbers) or (0,)


def install_blocker() -> Optional[str]:
    """Why this copy can't replace itself, or None if it can."""
    bundle = app_bundle()
    if bundle is None:
        return "Updates install only in the packaged app, not when running from source."
    path = str(bundle)
    if "/AppTranslocation/" in path or path.startswith("/Volumes/"):
        return "Move MoneyTalks to your Applications folder to turn on updates."
    if not os.access(bundle.parent, os.W_OK):
        return f"MoneyTalks can't write to {bundle.parent}, so it can't update itself."
    return None


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def _open(url: str, accept: str = "application/vnd.github+json"):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    context = ssl.create_default_context(cafile=certifi.where())
    return urllib.request.urlopen(request, context=context, timeout=30)


def fetch_latest() -> Release:
    with _open(LATEST_RELEASE_URL) as response:
        data = json.load(response)
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if asset is None:
        raise UpdateError(f"the latest release has no {ASSET_NAME}")
    return Release(
        version=data["tag_name"].lstrip("v"),
        page_url=data["html_url"],
        asset_url=asset["browser_download_url"],
        size=int(asset.get("size") or 0),
    )


def download(release: Release, progress: Callable[[int], None]) -> Path:
    """Download the release's disk image; ``progress`` receives whole percents."""
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    target = UPDATES_DIR / f"MoneyTalks-{release.version}.dmg"
    partial = target.with_suffix(".part")
    last = -1
    with _open(release.asset_url, accept="application/octet-stream") as response, open(partial, "wb") as f:
        total = int(response.headers.get("Content-Length") or release.size or 0)
        done = 0
        while chunk := response.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            percent = int(done * 100 / total) if total else 0
            if percent != last:
                progress(percent)
                last = percent
    partial.replace(target)
    return target


# ---------------------------------------------------------------------------
# Staging and installing
# ---------------------------------------------------------------------------

def _run(cmd: list[str], check: bool = True) -> None:
    subprocess.run(cmd, check=check, capture_output=True)


def stage(dmg: Path, version: str) -> Path:
    """Copy MoneyTalks.app out of the disk image, verify it, return its path."""
    staged = UPDATES_DIR / version / "MoneyTalks.app"
    shutil.rmtree(staged.parent, ignore_errors=True)
    staged.parent.mkdir(parents=True)
    mount = Path(tempfile.mkdtemp(prefix="moneytalks-update-"))
    try:
        _run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(dmg)])
        try:
            _run(["ditto", str(mount / "MoneyTalks.app"), str(staged)])
        finally:
            _run(["hdiutil", "detach", str(mount)], check=False)
    finally:
        shutil.rmtree(mount, ignore_errors=True)
    dmg.unlink(missing_ok=True)

    _run(["codesign", "--verify", "--deep", "--strict", str(staged)])
    with open(staged / "Contents" / "Info.plist", "rb") as f:
        staged_version = plistlib.load(f).get("CFBundleShortVersionString", "")
    if version_key(staged_version) != version_key(version):
        raise UpdateError(f"downloaded app reports version {staged_version}, expected {version}")
    return staged


def launch_installer(staged: Path, relaunch: bool) -> None:
    """Start the swap script; it runs once this process has exited."""
    target = app_bundle()
    if target is None:
        raise UpdateError("not running from an installed app")
    script = UPDATES_DIR / "install.sh"
    script.write_text(_INSTALL_SCRIPT)
    script.chmod(0o755)
    subprocess.Popen(
        ["/bin/sh", str(script), str(os.getpid()), str(staged), str(target), "1" if relaunch else "0"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


# ---------------------------------------------------------------------------
# Background controller used by the app window
# ---------------------------------------------------------------------------

class Updater:
    """Check → download → stage in a background thread.

    State changes are reported to ``on_change`` as a dict with a ``state`` of
    idle | checking | downloading | ready | current | blocked | error.
    Automatic checks stay quiet unless an update is found; manual checks
    ("Check for Updates…") report every outcome.
    """

    def __init__(self, on_change: Callable[[dict], None]):
        self._on_change = on_change
        self._lock = threading.Lock()
        self._busy = False
        self.staged: Optional[Path] = None
        self.staged_version: Optional[str] = None
        self.state: dict = {"state": "idle", "current": current_version()}

    def _set(self, state: str, **extra) -> None:
        self.state = {"state": state, "current": current_version(), **extra}
        self._on_change(self.state)

    def check(self, manual: bool = False) -> None:
        """Start a check in the background; ignored while one is running."""
        with self._lock:
            if self._busy:
                return
            self._busy = True
        threading.Thread(target=self._check, args=(manual,), daemon=True).start()

    def start_automatic_checks(self) -> None:
        def loop() -> None:
            time.sleep(FIRST_CHECK_DELAY_SECONDS)
            while True:
                self.check()
                time.sleep(CHECK_EVERY_SECONDS)

        threading.Thread(target=loop, daemon=True).start()

    def install_on_quit(self) -> None:
        if self.staged:
            launch_installer(self.staged, relaunch=False)

    def restart_to_update(self) -> bool:
        if not self.staged:
            return False
        launch_installer(self.staged, relaunch=True)
        return True

    def _check(self, manual: bool) -> None:
        try:
            if self.staged:
                self._set("ready", version=self.staged_version)
                return
            if manual:
                self._set("checking")
            release = fetch_latest()
            if version_key(release.version) <= version_key(current_version()):
                self._set("current" if manual else "idle")
                return
            blocker = install_blocker()
            if blocker:
                self._set("blocked", version=release.version, message=blocker, url=release.page_url)
                return
            self._set("downloading", version=release.version, progress=0)
            dmg = download(release, lambda p: self._set("downloading", version=release.version, progress=p))
            self.staged = stage(dmg, release.version)
            self.staged_version = release.version
            self._set("ready", version=release.version)
        except Exception as exc:  # network down, GitHub unavailable, bad download…
            if manual:
                self._set("error", message=f"{type(exc).__name__}: {exc}")
            else:
                self._set("idle")
        finally:
            with self._lock:
                self._busy = False
