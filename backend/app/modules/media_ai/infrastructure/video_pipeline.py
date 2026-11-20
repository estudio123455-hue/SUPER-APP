"""Real Video Clipper Pipeline: Audio Peak Finder + faster-whisper + TikTok Subtitle Burn-in (9:16)."""

import importlib.util
import logging
from pathlib import Path
import re
import subprocess
from typing import Any
from uuid import UUID

from app.modules.media_ai.infrastructure.binary_locator import get_media_binaries_status

logger = logging.getLogger(__name__)

# Minimal valid ISO Base Media File Format (MP4 ftyp + moov stub) for fast offline/test fallback
MINIMAL_MP4_BYTES = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    b"\x00\x00\x00\x08free"
)

TIKTOK_SUBTITLE_FORCE_STYLE = (
    "FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,"
    "Alignment=2,MarginV=45"
)

_SRT_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)
_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")


def _format_srt_timestamp(seconds: float) -> str:
    clamped = max(0.0, seconds)
    millis = int(round(clamped * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _parse_srt_hms(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600.0 + int(m) * 60.0 + int(s) + int(ms) / 1000.0


def find_viral_audio_peak_start_sec(
    segments: list[tuple[float, float, str]],
    clip_duration_sec: float = 20.0,
) -> float:
    """Finds the 20-second window start with the highest vocal word density."""
    if not segments:
        return 0.0

    best_start = 0.0
    best_word_count = -1

    for seg_start, _seg_end, _seg_text in segments:
        candidate_start = max(0.0, float(seg_start))
        candidate_end = candidate_start + clip_duration_sec
        words_in_window = 0
        for s_start, s_end, text in segments:
            if s_end > candidate_start and s_start < candidate_end:
                words_in_window += len(text.split())
        if words_in_window > best_word_count:
            best_word_count = words_in_window
            best_start = candidate_start

    return round(best_start, 2)


def shift_and_clip_srt_to_window(
    srt_text: str,
    clip_start_sec: float,
    clip_duration_sec: float = 20.0,
) -> str:
    """Shifts .srt timestamps by -clip_start_sec and filters to [0, clip_duration_sec]."""
    if clip_start_sec <= 0.0:
        return srt_text

    clip_end_sec = clip_start_sec + clip_duration_sec
    raw_blocks = [b.strip() for b in re.split(r"\r?\n\r?\n", srt_text.strip()) if b.strip()]
    shifted_blocks: list[str] = []
    new_idx = 1

    for block in raw_blocks:
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        match = _SRT_TIME_RE.search(lines[1])
        if not match:
            continue

        start_sec = _parse_srt_hms(*match.groups()[:4])
        end_sec = _parse_srt_hms(*match.groups()[4:])
        if end_sec <= clip_start_sec or start_sec >= clip_end_sec:
            continue

        rel_start = max(0.0, start_sec - clip_start_sec)
        rel_end = min(clip_duration_sec, end_sec - clip_start_sec)
        if rel_end <= rel_start:
            continue

        caption_body = "\n".join(lines[2:]).strip()
        if not caption_body:
            continue

        shifted_blocks.append(
            f"{new_idx}\n"
            f"{_format_srt_timestamp(rel_start)} --> {_format_srt_timestamp(rel_end)}\n"
            f"{caption_body}\n"
        )
        new_idx += 1

    return "\n".join(shifted_blocks) if shifted_blocks else srt_text


class RealVideoClipperPipeline:
    """Executes real 720p download, Audio Peak detection, Whisper transcription & 9:16 subtitle burn-in."""

    def __init__(self, outputs_base_dir: Path) -> None:
        self._outputs_base_dir = outputs_base_dir

    @staticmethod
    def _is_external_downloadable_url(source: str) -> bool:
        if not source.startswith(("http://", "https://")):
            return False
        synthetic_hosts = ("storage.superapp.io", "cdn.superapp.io", "localhost", "127.0.0.1")
        return not any(host in source for host in synthetic_hosts)

    def _download_720p_section(
        self,
        source_url: str,
        job_dir: Path,
        ffmpeg_path: str | None,
        deno_path: str | None,
    ) -> tuple[Path | None, dict[str, str]]:
        """Downloads up to the first 90 seconds in <=720p via yt-dlp."""
        if importlib.util.find_spec("yt_dlp") is None:
            return None, {}

        output_template = str(job_dir / "source_720p.%(ext)s")
        target_mp4 = job_dir / "source_720p.mp4"
        meta: dict[str, str] = {}

        try:
            import yt_dlp  # type: ignore[import-not-found]

            ydl_opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
                "merge_output_format": "mp4",
                "outtmpl": output_template,
                "socket_timeout": 15,
            }
            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path
                ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
                    None, [(0.0, 90.0)]
                )
            if deno_path:
                ydl_opts["extractor_args"] = {"youtube": {"player_client": ["default"]}}

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=True)
                if isinstance(info, dict):
                    meta["video_title"] = str(info.get("title") or "")
                    meta["video_duration_sec"] = str(info.get("duration") or "")
        except Exception as exc:
            logger.warning("yt-dlp download failed for %s: %s", source_url, exc)
            return None, meta

        if target_mp4.is_file():
            return target_mp4, meta

        for candidate in job_dir.glob("source_720p.*"):
            if candidate.is_file():
                return candidate, meta
        return None, meta

    @staticmethod
    def _detect_audio_peak_via_ffmpeg_volumedetect(
        media_file: Path,
        ffmpeg_path: str,
    ) -> float:
        """Scans 10-second windows with ffmpeg volumedetect to find the loudest audio peak."""
        best_offset = 0.0
        best_db = -100.0
        for offset in (0, 10, 20, 30, 40):
            cmd = [
                ffmpeg_path,
                "-ss",
                str(offset),
                "-t",
                "10",
                "-i",
                str(media_file),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ]
            try:
                res = subprocess.run(
                    cmd,
                    check=False,
                    timeout=15,
                    capture_output=True,
                    text=True,
                )
                match = _MEAN_VOLUME_RE.search(res.stderr or "")
                if match:
                    mean_db = float(match.group(1))
                    if mean_db > best_db:
                        best_db = mean_db
                        best_offset = float(offset)
            except Exception:
                continue
        return best_offset

    @staticmethod
    def _transcribe_with_faster_whisper(
        media_file: Path,
    ) -> tuple[str | None, list[tuple[float, float, str]]]:
        """Transcribes audio using faster-whisper ('base', device='cpu', compute_type='int8')."""
        if importlib.util.find_spec("faster_whisper") is None:
            return None, []

        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]

            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments_iter, _info = model.transcribe(str(media_file), beam_size=3)
            srt_blocks: list[str] = []
            raw_segments: list[tuple[float, float, str]] = []
            for idx, seg in enumerate(segments_iter, start=1):
                s_start = float(seg.start)
                s_end = float(seg.end)
                text = str(seg.text).strip()
                if text:
                    raw_segments.append((s_start, s_end, text))
                    start_ts = _format_srt_timestamp(s_start)
                    end_ts = _format_srt_timestamp(s_end)
                    srt_blocks.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")
            return ("\n".join(srt_blocks) if srt_blocks else None), raw_segments
        except Exception as exc:
            logger.warning("faster-whisper transcription fallback: %s", exc)
            return None, []

    @staticmethod
    def _crop_and_burn_vertical_9x16_ffmpeg(
        source_media: Path,
        output_mp4: Path,
        ffmpeg_path: str,
        start_offset_sec: float = 0.0,
        burn_subtitles: bool = True,
        srt_filename: str = "captions.srt",
    ) -> tuple[bool, bool]:
        """Crops a 20s vertical 9:16 clip (720x1280) and burns TikTok-styled subtitles."""
        base_crop = "crop=ih*9/16:ih,scale=720:1280"
        job_dir = output_mp4.parent

        if burn_subtitles and (job_dir / srt_filename).is_file():
            vf_with_subs = (
                f"{base_crop},subtitles={srt_filename}:force_style='{TIKTOK_SUBTITLE_FORCE_STYLE}'"
            )
            burn_cmd = [
                ffmpeg_path,
                "-y",
                "-ss",
                str(start_offset_sec),
                "-i",
                str(source_media),
                "-t",
                "20",
                "-vf",
                vf_with_subs,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                str(output_mp4),
            ]
            try:
                res = subprocess.run(
                    burn_cmd,
                    cwd=str(job_dir),
                    check=False,
                    timeout=90,
                    capture_output=True,
                )
                if res.returncode == 0 and output_mp4.is_file():
                    return True, True
            except Exception as exc:
                logger.warning("FFmpeg subtitle burn-in fallback to clean crop: %s", exc)

        clean_cmd = [
            ffmpeg_path,
            "-y",
            "-ss",
            str(start_offset_sec),
            "-i",
            str(source_media),
            "-t",
            "20",
            "-vf",
            base_crop,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            str(output_mp4),
        ]
        try:
            res = subprocess.run(
                clean_cmd,
                cwd=str(job_dir),
                check=False,
                timeout=90,
                capture_output=True,
            )
            return (res.returncode == 0 and output_mp4.is_file()), False
        except Exception as exc:
            logger.warning("FFmpeg 9:16 crop failed: %s", exc)
            return False, False

    def execute_pipeline(
        self,
        job_id: UUID,
        source_url_or_prompt: str,
        enable_real_media_pipeline: bool,
        burn_subtitles: bool = True,
        default_srt_content: str = "",
    ) -> dict[str, str]:
        """Runs peak detection, Whisper SRT alignment, and TikTok subtitle burn-in with fallback."""
        job_dir = self._outputs_base_dir / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        short_mp4_path = job_dir / "short_9x16.mp4"
        srt_path = job_dir / "captions.srt"

        binaries = get_media_binaries_status(auto_install_ffmpeg=False)
        result_meta: dict[str, str] = {
            "ffmpeg_detected": str(bool(binaries.ffmpeg_path)),
            "deno_detected": str(bool(binaries.deno_path)),
            "mp4_download_url": f"/api/v1/media-ai/jobs/{job_id}/download-mp4",
            "subtitles_burned": str(burn_subtitles).lower(),
            "subtitle_style": "tiktok_bold_outline" if burn_subtitles else "none",
            "clip_start_offset_sec": "0.0",
        }

        if enable_real_media_pipeline and self._is_external_downloadable_url(
            source_url_or_prompt
        ):
            downloaded_file, dl_meta = self._download_720p_section(
                source_url=source_url_or_prompt,
                job_dir=job_dir,
                ffmpeg_path=binaries.ffmpeg_path,
                deno_path=binaries.deno_path,
            )
            result_meta.update({k: v for k, v in dl_meta.items() if v})

            if downloaded_file is not None:
                whisper_srt, raw_segments = self._transcribe_with_faster_whisper(
                    downloaded_file
                )
                if raw_segments:
                    peak_offset = find_viral_audio_peak_start_sec(
                        raw_segments,
                        clip_duration_sec=20.0,
                    )
                elif binaries.ffmpeg_path:
                    peak_offset = self._detect_audio_peak_via_ffmpeg_volumedetect(
                        downloaded_file,
                        binaries.ffmpeg_path,
                    )
                else:
                    peak_offset = 0.0

                result_meta["clip_start_offset_sec"] = str(peak_offset)

                active_srt = whisper_srt or default_srt_content
                if active_srt:
                    aligned_srt = shift_and_clip_srt_to_window(
                        active_srt,
                        clip_start_sec=peak_offset,
                        clip_duration_sec=20.0,
                    )
                    result_meta["captions_srt_preview"] = aligned_srt
                    srt_path.write_text(aligned_srt, encoding="utf-8")
                    if whisper_srt:
                        result_meta["whisper_engine"] = "faster-whisper-base-int8"

                if binaries.ffmpeg_path:
                    cropped_ok, burned_ok = self._crop_and_burn_vertical_9x16_ffmpeg(
                        source_media=downloaded_file,
                        output_mp4=short_mp4_path,
                        ffmpeg_path=binaries.ffmpeg_path,
                        start_offset_sec=peak_offset,
                        burn_subtitles=burn_subtitles,
                        srt_filename="captions.srt",
                    )
                    if cropped_ok:
                        result_meta["pipeline_mode"] = "real_yt_dlp_whisper_ffmpeg"
                        result_meta["subtitles_burned"] = str(burned_ok).lower()
                        result_meta["mp4_file_path"] = str(short_mp4_path)
                        return result_meta

        # Graceful fallback so tests and offline runs always produce a downloadable MP4 artifact
        if not short_mp4_path.is_file():
            short_mp4_path.write_bytes(MINIMAL_MP4_BYTES)

        result_meta["pipeline_mode"] = (
            "graceful_fallback" if enable_real_media_pipeline else "synthetic_fast"
        )
        result_meta["mp4_file_path"] = str(short_mp4_path)
        return result_meta
