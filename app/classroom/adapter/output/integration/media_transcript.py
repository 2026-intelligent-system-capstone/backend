import asyncio
import subprocess
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from openai import AsyncOpenAI

from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
)
from core.config import config


@dataclass(frozen=True)
class MediaTranscriptSegment:
    text: str
    start_seconds: float
    duration_seconds: float


class MediaTranscriptExtractorPort(Protocol):
    async def extract_transcript(
        self,
        *,
        content: bytes,
        file_name: str,
    ) -> list[MediaTranscriptSegment]: ...


class FfmpegOpenAIMediaTranscriptExtractor:
    async def extract_transcript(
        self,
        *,
        content: bytes,
        file_name: str,
    ) -> list[MediaTranscriptSegment]:
        _ = file_name
        if not config.MEDIA_TRANSCRIPTION_ENABLED:
            raise ClassroomMaterialIngestDomainException(
                message="미디어 transcript 추출이 비활성화되어 있습니다."
            )
        if len(content) > config.MEDIA_MAX_BYTES:
            raise ClassroomMaterialIngestDomainException(
                message="미디어 파일 크기가 허용 범위를 초과했습니다."
            )

        audio_bytes = await asyncio.to_thread(self._extract_audio, content)
        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        transcription = await client.audio.transcriptions.create(
            model=config.OPENAI_TRANSCRIPTION_MODEL,
            file=("audio.wav", BytesIO(audio_bytes), "audio/wav"),
            response_format="verbose_json",
        )
        return self._convert_transcription(transcription)

    def _extract_audio(self, content: bytes) -> bytes:
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "audio.wav"
            try:
                process = subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-protocol_whitelist",
                        "file,pipe",
                        "-i",
                        "pipe:0",
                        "-vn",
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        "-f",
                        "wav",
                        "-fs",
                        str(config.MEDIA_EXTRACTED_AUDIO_MAX_BYTES),
                        str(output_path),
                    ],
                    input=content,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=config.MEDIA_FFMPEG_TIMEOUT_SECONDS,
                    check=False,
                    shell=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ClassroomMaterialIngestDomainException(
                    message="미디어 오디오 추출 시간이 초과되었습니다."
                ) from exc
            except OSError as exc:
                raise ClassroomMaterialIngestDomainException(
                    message="미디어 오디오 추출 도구를 실행하지 못했습니다."
                ) from exc

            if process.returncode != 0 or not output_path.exists():
                raise ClassroomMaterialIngestDomainException(
                    message="미디어 오디오를 추출하지 못했습니다."
                )
            audio_size = output_path.stat().st_size
            if audio_size == 0:
                raise ClassroomMaterialIngestDomainException(
                    message="미디어 오디오를 추출하지 못했습니다."
                )
            if audio_size >= config.MEDIA_EXTRACTED_AUDIO_MAX_BYTES:
                raise ClassroomMaterialIngestDomainException(
                    message="미디어 오디오 크기가 허용 범위를 초과했습니다."
                )
            return output_path.read_bytes()

    def _convert_transcription(
        self,
        transcription: object,
    ) -> list[MediaTranscriptSegment]:
        segments = self._read_value(transcription, "segments", []) or []
        converted_segments: list[MediaTranscriptSegment] = []
        for segment in segments:
            text = str(self._read_value(segment, "text", "")).strip()
            if not text:
                continue
            start_seconds = float(
                self._read_value(segment, "start", 0.0) or 0.0
            )
            end_seconds = float(self._read_value(segment, "end", 0.0) or 0.0)
            converted_segments.append(
                MediaTranscriptSegment(
                    text=text,
                    start_seconds=start_seconds,
                    duration_seconds=max(0.0, end_seconds - start_seconds),
                )
            )
        if converted_segments:
            return converted_segments

        text = str(self._read_value(transcription, "text", "")).strip()
        if not text:
            return []
        return [
            MediaTranscriptSegment(
                text=text,
                start_seconds=0.0,
                duration_seconds=0.0,
            )
        ]

    def _read_value(
        self,
        source: object,
        key: str,
        default: object,
    ) -> object:
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)
