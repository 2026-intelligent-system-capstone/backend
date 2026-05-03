import pytest

from app.classroom.domain.service import (
    evaluate_classroom_material_source,
    validate_classroom_material_source_url,
)


@pytest.mark.parametrize(
    "file_name",
    [
        "lecture.pdf",
        "lecture.pptx",
        "lecture.docx",
        "lecture.hwpx",
        "lecture.avi",
        "lecture.mp4",
        "lecture.zip",
    ],
)
def test_supported_file_extensions_are_ingestible(file_name: str):
    capability = evaluate_classroom_material_source(
        file_name=file_name,
        mime_type="application/octet-stream",
    )

    assert capability.supported is True
    assert capability.reason is None


@pytest.mark.parametrize(
    "file_name",
    [
        "lecture.txt",
        "lecture.md",
        "lecture.csv",
        "lecture.json",
        "lecture.xml",
    ],
)
def test_text_file_extensions_are_ingestible(file_name: str):
    capability = evaluate_classroom_material_source(
        file_name=file_name,
        mime_type="application/octet-stream",
    )

    assert capability.supported is True
    assert capability.reason is None
    assert capability.source_type == "file"


@pytest.mark.parametrize(
    ("mime_type", "expected_extension"),
    [
        ("text/plain", "txt"),
        ("text/markdown", "md"),
        ("text/csv", "csv"),
        ("application/json", "json"),
        ("application/xml", "xml"),
        ("text/xml", "xml"),
    ],
)
def test_text_mime_types_without_extension_are_ingestible(
    mime_type: str,
    expected_extension: str,
):
    capability = evaluate_classroom_material_source(
        file_name="lecture",
        mime_type=mime_type,
    )

    assert capability.supported is True
    assert capability.extension == expected_extension
    assert capability.source_type == "file"


@pytest.mark.parametrize(
    "file_name",
    [
        "lecture.pdf",
        "lecture.pptx",
        "lecture.docx",
        "lecture.hwpx",
        "lecture.avi",
        "lecture.mp4",
        "lecture.zip",
    ],
)
def test_octet_stream_with_supported_extension_is_ingestible(
    file_name: str,
):
    capability = evaluate_classroom_material_source(
        file_name=file_name,
        mime_type="application/octet-stream",
    )

    assert capability.supported is True
    assert capability.extension == file_name.rsplit(".", maxsplit=1)[1]


@pytest.mark.parametrize(
    "file_name",
    ["legacy.ppt", "legacy.doc", "legacy.hwp"],
)
def test_legacy_file_extensions_are_not_supported(file_name: str):
    capability = evaluate_classroom_material_source(
        file_name=file_name,
        mime_type="application/octet-stream",
    )

    assert capability.supported is False
    assert capability.reason == "현재 지원하지 않는 강의 자료 형식입니다."


@pytest.mark.parametrize(
    "mime_type",
    [
        "application/haansofthwpx",
        "application/haansofthwp",
        "application/x-hwpml",
    ],
)
def test_hwpx_mime_without_extension_is_ingestible(mime_type: str):
    capability = evaluate_classroom_material_source(
        file_name="lecture",
        mime_type=mime_type,
    )

    assert capability.supported is True
    assert capability.extension == "hwpx"


@pytest.mark.parametrize(
    "source_url",
    [
        "http://www.youtube.com/watch?v=demo",
        "http://youtu.be/demo",
        "http://example.com/lecture",
    ],
)
def test_http_links_are_accepted_but_not_ingestible(source_url: str):
    capability = evaluate_classroom_material_source(source_url=source_url)

    assert capability.supported is False
    assert capability.reason == "현재 지원하지 않는 강의 자료 형식입니다."
    assert capability.source_type == "link"


def test_general_https_link_is_accepted_but_not_ingestible():
    capability = evaluate_classroom_material_source(
        source_url="https://example.com/lecture",
    )

    assert capability.supported is False
    assert capability.reason == "현재 지원하지 않는 강의 자료 형식입니다."
    assert capability.source_type == "link"


@pytest.mark.parametrize(
    "source_url",
    [
        "https://www.youtube.com/watch?v=demo",
        "https://m.youtube.com/watch?v=demo",
        "https://youtu.be/demo",
    ],
)
def test_youtube_links_are_supported(source_url: str):
    capability = evaluate_classroom_material_source(source_url=source_url)

    assert capability.supported is True
    assert capability.reason is None
    assert capability.source_type == "youtube"


@pytest.mark.parametrize(
    "source_url",
    [
        "http://localhost:3000/material",
        "http://127.0.0.1/material",
        "http://192.168.0.10/material",
        "https://www.youtube.com/watch?v=demo",
    ],
)
def test_material_source_url_validation_allows_local_and_private_urls(
    source_url: str,
):
    validate_classroom_material_source_url(source_url)
