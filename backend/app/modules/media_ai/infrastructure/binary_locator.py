"""Windows binary auto-locator for FFmpeg and Deno (used by yt-dlp and video clipping)."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MediaBinariesStatus:
    """Resolved absolute paths for external media processing binaries."""

    ffmpeg_path: str | None
    deno_path: str | None


def _search_common_windows_dirs(binary_name: str) -> str | None:
    """Searches PATH first, then typical WinGet and user install directories on Windows."""
    in_path = shutil.which(binary_name)
    if in_path:
        return in_path

    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    user_profile = Path(os.environ.get("USERPROFILE", ""))

    candidate_roots = [
        local_app_data / "Microsoft" / "WinGet" / "Links",
        local_app_data / "Microsoft" / "WinGet" / "Packages",
        user_profile / ".deno" / "bin",
        user_profile / "scoop" / "shims",
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
    ]

    exe_name = binary_name if binary_name.endswith(".exe") else f"{binary_name}.exe"

    for root in candidate_roots:
        if not root.exists():
            continue
        direct = root / exe_name
        if direct.is_file():
            return str(direct)
        try:
            for match in root.rglob(exe_name):
                if match.is_file():
                    return str(match)
        except OSError:
            continue

    return None


def locate_ffmpeg(auto_install_via_winget: bool = False) -> str | None:
    """Locates ffmpeg.exe on Windows, optionally attempting silent winget installation."""
    found = _search_common_windows_dirs("ffmpeg.exe")
    if found:
        return found

    if auto_install_via_winget and shutil.which("winget"):
        try:
            subprocess.run(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "Gyan.FFmpeg",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--silent",
                ],
                check=False,
                timeout=120,
                capture_output=True,
            )
            return _search_common_windows_dirs("ffmpeg.exe")
        except Exception as exc:
            logger.warning("Winget FFmpeg auto-install skipped: %s", exc)

    logger.warning(
        "ffmpeg.exe was not found in PATH or WinGet packages. Falling back to synthetic clip generation."
    )
    return None


def locate_deno() -> str | None:
    """Locates deno.exe on Windows (used by yt-dlp for YouTube JS challenge solving)."""
    return _search_common_windows_dirs("deno.exe")


def get_media_binaries_status(
    auto_install_ffmpeg: bool = False,
) -> MediaBinariesStatus:
    """Returns the current detected paths for ffmpeg.exe and deno.exe."""
    return MediaBinariesStatus(
        ffmpeg_path=locate_ffmpeg(auto_install_via_winget=auto_install_ffmpeg),
        deno_path=locate_deno(),
    )
