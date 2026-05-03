import ipaddress
import re
import socket
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol
from urllib.parse import urlparse

import yt_dlp
from openai import OpenAI

from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
)
from core.config import config

YOUTUBE_SUBTITLE_DOWNLOAD_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
}
GOOGLEVIDEO_HOST_SUFFIX = ".googlevideo.com"
DOWNLOAD_CHUNK_SIZE = 8192
YOUTUBE_VIDEO_INFO_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}
YOUTUBE_VIDEO_INFO_ERROR_MESSAGE = "YouTube 영상 정보를 조회하지 못했습니다."
YOUTUBE_SUBTITLE_DOWNLOAD_ERROR_MESSAGE = (
    "YouTube subtitle을 다운로드하지 못했습니다."
)
YOUTUBE_SUBTITLE_FORMAT_ERROR_MESSAGE = (
    "YouTube subtitle 형식이 올바르지 않습니다."
)
YOUTUBE_AUDIO_SIZE_LIMIT_ERROR_MESSAGE = (
    "YouTube 오디오 크기가 허용 범위를 초과했습니다."
)


@dataclass(frozen=True)
class YoutubeTranscriptSegment:
    text: str
    start_seconds: float
    duration_seconds: float


class YoutubeTranscriptExtractorPort(Protocol):
    def extract_transcript(
        self,
        *,
        url: str,
    ) -> list[YoutubeTranscriptSegment]:
        """Extract timestamped transcript segments from a YouTube URL."""


class YtDlpYoutubeTranscriptExtractor(YoutubeTranscriptExtractorPort):
    def extract_transcript(
        self,
        *,
        url: str,
    ) -> list[YoutubeTranscriptSegment]:
        _validate_youtube_video_info_url(url)
        info = self._extract_video_info(url=url)
        duration = _coerce_float(info.get("duration"))
        if (
            duration is not None
            and duration > config.YOUTUBE_MAX_DURATION_SECONDS
        ):
            raise ClassroomMaterialIngestDomainException(
                message="YouTube 영상 길이가 허용 범위를 초과했습니다."
            )

        subtitle_url = self._select_subtitle_url(info=info)
        if subtitle_url is None:
            if config.YOUTUBE_AUDIO_TRANSCRIPTION_ENABLED:
                audio_url = _extract_audio_download_url(info=info)
                return self._extract_audio_transcription_segments(url=audio_url)
            return []

        subtitle_text = self._download_subtitle_text(url=subtitle_url)
        try:
            return _parse_vtt_segments(subtitle_text)
        except ClassroomMaterialIngestDomainException:
            raise
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message=YOUTUBE_SUBTITLE_FORMAT_ERROR_MESSAGE
            ) from exc

    def _extract_video_info(self, *, url: str) -> dict:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": config.YOUTUBE_TRANSCRIPT_LANGUAGES,
            "subtitlesformat": "vtt/best",
            "socket_timeout": config.YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS,
            "extract_flat": False,
            "noplaylist": True,
        }
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=False)
                return downloader.sanitize_info(info)
        except ClassroomMaterialIngestDomainException:
            raise
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message=YOUTUBE_VIDEO_INFO_ERROR_MESSAGE
            ) from exc

    def _download_subtitle_text(self, *, url: str) -> str:
        try:
            _validate_subtitle_download_url(url)
            opener = urllib.request.build_opener(_SafeSubtitleRedirectHandler())
            with opener.open(
                url,
                timeout=config.YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS,
            ) as response:
                raw = response.read(config.YOUTUBE_SUBTITLE_MAX_BYTES + 1)
            if len(raw) > config.YOUTUBE_SUBTITLE_MAX_BYTES:
                raise ClassroomMaterialIngestDomainException(
                    message=YOUTUBE_SUBTITLE_DOWNLOAD_ERROR_MESSAGE
                )
            return raw.decode("utf-8", errors="ignore")
        except ClassroomMaterialIngestDomainException:
            raise
        except Exception as exc:
            raise ClassroomMaterialIngestDomainException(
                message=YOUTUBE_SUBTITLE_DOWNLOAD_ERROR_MESSAGE
            ) from exc

    def _extract_audio_transcription_segments(
        self,
        *,
        url: str,
    ) -> list[YoutubeTranscriptSegment]:
        audio_path = self._download_audio(url=url)
        try:
            with audio_path.open("rb") as audio_file:
                transcription = OpenAI(
                    api_key=config.OPENAI_API_KEY
                ).audio.transcriptions.create(
                    model=config.OPENAI_TRANSCRIPTION_MODEL,
                    file=audio_file,
                    response_format="verbose_json",
                )
        finally:
            _unlink_file(audio_path)
        return _convert_audio_transcription(transcription)

    def _download_audio(self, *, url: str) -> Path:
        audio_path: Path | None = None
        try:
            _validate_subtitle_download_url(url)
            opener = urllib.request.build_opener(_SafeSubtitleRedirectHandler())
            with opener.open(
                url,
                timeout=config.YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS,
            ) as response:
                with NamedTemporaryFile(delete=False, suffix=".audio") as file:
                    audio_path = Path(file.name)
                    downloaded_size = 0
                    while True:
                        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        downloaded_size += len(chunk)
                        if downloaded_size > config.YOUTUBE_AUDIO_MAX_BYTES:
                            raise ClassroomMaterialIngestDomainException(
                                message=YOUTUBE_AUDIO_SIZE_LIMIT_ERROR_MESSAGE
                            )
                        file.write(chunk)
                    return audio_path
        except ClassroomMaterialIngestDomainException:
            if audio_path is not None:
                _unlink_file(audio_path)
            raise
        except Exception as exc:
            if audio_path is not None:
                _unlink_file(audio_path)
            raise ClassroomMaterialIngestDomainException(
                message="YouTube 오디오를 다운로드하지 못했습니다."
            ) from exc

    def _select_subtitle_url(self, *, info: dict) -> str | None:
        for subtitle_group_name in ("subtitles", "automatic_captions"):
            subtitle_url = _find_subtitle_url(
                subtitles=info.get(subtitle_group_name),
                languages=config.YOUTUBE_TRANSCRIPT_LANGUAGES,
            )
            if subtitle_url is not None:
                return subtitle_url
        return None


class _SafeSubtitleRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        _validate_subtitle_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_youtube_video_info_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in YOUTUBE_VIDEO_INFO_HOSTS:
        raise ClassroomMaterialIngestDomainException(
            message=YOUTUBE_VIDEO_INFO_ERROR_MESSAGE
        )


def _validate_subtitle_download_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    normalized_host = host.lower()
    if parsed.scheme != "https" or not _is_allowed_subtitle_host(
        normalized_host
    ):
        raise ClassroomMaterialIngestDomainException(
            message=YOUTUBE_SUBTITLE_DOWNLOAD_ERROR_MESSAGE
        )

    try:
        address_infos = socket.getaddrinfo(normalized_host, parsed.port or 443)
    except socket.gaierror as exc:
        raise ClassroomMaterialIngestDomainException(
            message=YOUTUBE_SUBTITLE_DOWNLOAD_ERROR_MESSAGE
        ) from exc

    for address_info in address_infos:
        socket_address = address_info[4]
        if not socket_address:
            continue
        ip_address = ipaddress.ip_address(socket_address[0])
        if _is_blocked_ip_address(ip_address):
            raise ClassroomMaterialIngestDomainException(
                message=YOUTUBE_SUBTITLE_DOWNLOAD_ERROR_MESSAGE
            )


def _is_allowed_subtitle_host(host: str) -> bool:
    return host in YOUTUBE_SUBTITLE_DOWNLOAD_HOSTS or host.endswith(
        GOOGLEVIDEO_HOST_SUFFIX
    )


def _is_blocked_ip_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address.is_reserved
        or address.is_multicast
    )


def _find_subtitle_url(
    *,
    subtitles: object,
    languages: list[str],
) -> str | None:
    if not isinstance(subtitles, dict):
        return None

    for language in _candidate_languages(
        languages=languages,
        subtitles=subtitles,
    ):
        candidates = subtitles.get(language)
        if not isinstance(candidates, list):
            continue
        best_candidate = _select_subtitle_candidate(candidates)
        if best_candidate is not None:
            return best_candidate
    return None


def _candidate_languages(*, languages: list[str], subtitles: dict) -> list[str]:
    exact_languages = [
        language for language in languages if language in subtitles
    ]
    related_languages = [
        subtitle_language
        for language in languages
        for subtitle_language in subtitles
        if subtitle_language.startswith(f"{language}-")
        or subtitle_language.startswith(f"{language}.")
    ]
    return [*exact_languages, *related_languages]


def _select_subtitle_candidate(candidates: list) -> str | None:
    vtt_candidate = _find_candidate_by_extension(
        candidates=candidates,
        extension="vtt",
    )
    if vtt_candidate is not None:
        return vtt_candidate
    return _find_candidate_by_extension(candidates=candidates, extension=None)


def _find_candidate_by_extension(
    *,
    candidates: list,
    extension: str | None,
) -> str | None:
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if extension is not None and candidate.get("ext") != extension:
            continue
        url = candidate.get("url")
        if isinstance(url, str) and url.strip():
            return url
    return None


def _extract_audio_download_url(*, info: dict) -> str:
    requested_downloads = info.get("requested_downloads")
    if isinstance(requested_downloads, list):
        url = _find_candidate_url(candidates=requested_downloads)
        if url is not None:
            return url

    formats = info.get("formats")
    if isinstance(formats, list):
        url = _find_audio_url(candidates=formats, require_audio_only=True)
        if url is not None:
            return url
        url = _find_audio_url(candidates=formats)
        if url is not None:
            return url

    raise ClassroomMaterialIngestDomainException(
        message="YouTube 오디오를 다운로드하지 못했습니다."
    )


def _find_candidate_url(*, candidates: list) -> str | None:
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        url = candidate.get("url")
        if isinstance(url, str) and url.strip():
            return url
    return None


def _find_audio_url(
    *,
    candidates: list,
    require_audio_only: bool = False,
) -> str | None:
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if require_audio_only and candidate.get("vcodec") != "none":
            continue
        if candidate.get("acodec") in {None, "none"}:
            continue
        url = candidate.get("url")
        if isinstance(url, str) and url.strip():
            return url
    return None


def _convert_audio_transcription(
    transcription: object,
) -> list[YoutubeTranscriptSegment]:
    segments = _read_value(transcription, "segments", []) or []
    converted_segments: list[YoutubeTranscriptSegment] = []
    for segment in segments:
        text = str(_read_value(segment, "text", "")).strip()
        if not text:
            continue
        start_seconds = float(_read_value(segment, "start", 0.0) or 0.0)
        end_seconds = float(_read_value(segment, "end", 0.0) or 0.0)
        converted_segments.append(
            YoutubeTranscriptSegment(
                text=text,
                start_seconds=start_seconds,
                duration_seconds=max(0.0, end_seconds - start_seconds),
            )
        )
    if converted_segments:
        return converted_segments

    text = str(_read_value(transcription, "text", "")).strip()
    if not text:
        return []
    return [
        YoutubeTranscriptSegment(
            text=text,
            start_seconds=0.0,
            duration_seconds=0.0,
        )
    ]


def _read_value(source: object, key: str, default: object) -> object:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _unlink_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _parse_vtt_segments(text: str) -> list[YoutubeTranscriptSegment]:
    segments: list[YoutubeTranscriptSegment] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        timestamp_index = _find_timestamp_line_index(lines)
        if timestamp_index is None:
            continue
        try:
            start_seconds, end_seconds = _parse_timestamp_range(
                lines[timestamp_index]
            )
        except ValueError:
            continue
        segment_text = _clean_segment_text(lines[timestamp_index + 1 :])
        if not segment_text:
            continue
        if len(segments) >= config.YOUTUBE_TRANSCRIPT_MAX_SEGMENTS:
            raise ClassroomMaterialIngestDomainException(
                message=YOUTUBE_SUBTITLE_FORMAT_ERROR_MESSAGE
            )
        current_text_length = sum(len(segment.text) for segment in segments)
        if (
            current_text_length + len(segment_text)
            > config.YOUTUBE_TRANSCRIPT_MAX_CHARS
        ):
            raise ClassroomMaterialIngestDomainException(
                message=YOUTUBE_SUBTITLE_FORMAT_ERROR_MESSAGE
            )
        segments.append(
            YoutubeTranscriptSegment(
                text=segment_text,
                start_seconds=start_seconds,
                duration_seconds=max(end_seconds - start_seconds, 0.0),
            )
        )
    return segments


def _find_timestamp_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if "-->" in line:
            return index
    return None


def _parse_timestamp_range(line: str) -> tuple[float, float]:
    start_text, end_text = line.split("-->", maxsplit=1)
    end_timestamp = end_text.strip().split(maxsplit=1)[0]
    return (
        _parse_timestamp(start_text.strip()),
        _parse_timestamp(end_timestamp),
    )


def _parse_timestamp(value: str) -> float:
    hours = 0
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    elif len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
    else:
        raise ValueError("invalid WebVTT timestamp")
    return hours * 3600 + minutes * 60 + seconds


def _clean_segment_text(lines: list[str]) -> str:
    text = "\n".join(lines)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
