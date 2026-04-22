from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)


def make_organization() -> Organization:
    return Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )


def test_organization_needs_code_change_only_for_different_code():
    organization = make_organization()

    assert organization.needs_code_change("univ_hansung") is False
    assert organization.needs_code_change("univ_hansung_new") is True


def test_organization_delete_marks_deleted_state():
    organization = make_organization()

    organization.delete()

    assert organization.is_deleted is True
    assert organization.is_active is False
