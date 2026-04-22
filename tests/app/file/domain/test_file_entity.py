from app.file.domain.entity.file import File, FileStatus


def make_file() -> File:
    return File(
        file_name="avatar.png",
        file_path="uploads/avatar.png",
        file_extension="png",
        file_size=1024,
        mime_type="image/png",
    )


def test_file_entity_creation():
    file = make_file()

    assert file.file_name == "avatar.png"
    assert file.status == FileStatus.PENDING


def test_file_activate():
    file = make_file()

    file.activate()

    assert file.status == FileStatus.ACTIVE


def test_file_update_changes_only_given_fields():
    file = make_file()

    file.update(file_name="resume.pdf", mime_type="application/pdf")

    assert file.file_name == "resume.pdf"
    assert file.mime_type == "application/pdf"
    assert file.file_path == "uploads/avatar.png"
    assert file.status == FileStatus.PENDING


def test_file_delete_returns_whether_storage_should_be_removed():
    file = make_file()

    should_remove = file.delete()

    assert should_remove is True
    assert file.status == FileStatus.DELETED


def test_file_delete_skips_storage_when_already_deleted():
    file = make_file()
    file.delete()

    should_remove = file.delete()

    assert should_remove is False
    assert file.status == FileStatus.DELETED
