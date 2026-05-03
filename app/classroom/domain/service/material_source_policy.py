from dataclasses import dataclass
from urllib.parse import urlparse

UNSUPPORTED_MATERIAL_FORMAT_REASON = "현재 지원하지 않는 강의 자료 형식입니다."
YOUTUBE_LINK_HOSTS = frozenset({
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
})

SUPPORTED_FILE_EXTENSIONS = frozenset({
    "avi",
    "csv",
    "docx",
    "hwpx",
    "json",
    "md",
    "mp4",
    "pdf",
    "pptx",
    "txt",
    "xml",
    "zip",
})
PPTX_MIME_TYPE = "".join((
    "application/",
    "vnd.openxmlformats-officedocument.presentationml.presentation",
))
DOCX_MIME_TYPE = "".join((
    "application/",
    "vnd.openxmlformats-officedocument.wordprocessingml.document",
))
MIME_TYPE_EXTENSIONS = {
    "application/haansofthwp": "hwpx",
    "application/haansofthwpx": "hwpx",
    "application/json": "json",
    "application/pdf": "pdf",
    "application/xml": "xml",
    "application/x-hwpml": "hwpx",
    "application/zip": "zip",
    DOCX_MIME_TYPE: "docx",
    PPTX_MIME_TYPE: "pptx",
    "text/csv": "csv",
    "text/markdown": "md",
    "text/plain": "txt",
    "text/xml": "xml",
    "video/avi": "avi",
    "video/mp4": "mp4",
    "video/x-msvideo": "avi",
}


@dataclass(frozen=True)
class ClassroomMaterialSourcePolicyResult:
    supported: bool
    reason: str | None = None
    extension: str | None = None
    source_type: str | None = None


def evaluate_classroom_material_source(
    *,
    file_name: str | None = None,
    mime_type: str | None = None,
    source_url: str | None = None,
) -> ClassroomMaterialSourcePolicyResult:
    if source_url is not None:
        return _evaluate_link_source(source_url=source_url)

    extension = _extract_extension(file_name=file_name)
    normalized_mime_type = _normalize_mime_type(mime_type=mime_type)
    extension = extension or MIME_TYPE_EXTENSIONS.get(normalized_mime_type)
    if extension in SUPPORTED_FILE_EXTENSIONS:
        return ClassroomMaterialSourcePolicyResult(
            supported=True,
            extension=extension,
            source_type="file",
        )

    return ClassroomMaterialSourcePolicyResult(
        supported=False,
        reason=UNSUPPORTED_MATERIAL_FORMAT_REASON,
        extension=extension,
        source_type="file",
    )


def _evaluate_link_source(
    *, source_url: str
) -> ClassroomMaterialSourcePolicyResult:
    parsed = urlparse(source_url)
    normalized_host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and normalized_host in YOUTUBE_LINK_HOSTS:
        return ClassroomMaterialSourcePolicyResult(
            supported=True,
            source_type="youtube",
        )
    return ClassroomMaterialSourcePolicyResult(
        supported=False,
        reason=UNSUPPORTED_MATERIAL_FORMAT_REASON,
        source_type="link",
    )


def _extract_extension(*, file_name: str | None) -> str | None:
    if file_name is None:
        return None

    normalized_file_name = file_name.strip().lower()
    if "." not in normalized_file_name:
        return None
    return normalized_file_name.rsplit(".", maxsplit=1)[1]


def _normalize_mime_type(*, mime_type: str | None) -> str:
    if mime_type is None:
        return ""
    return mime_type.strip().lower()
