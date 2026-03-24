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


def test_file_delete():
    file = make_file()

    file.delete()

    assert file.status == FileStatus.DELETED
