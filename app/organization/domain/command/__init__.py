from pydantic import BaseModel

from app.organization.domain.entity import OrganizationAuthProvider


class CreateOrganizationCommand(BaseModel):
    code: str
    name: str
    auth_provider: OrganizationAuthProvider
    is_active: bool = True


class UpdateOrganizationCommand(BaseModel):
    code: str | None = None
    name: str | None = None
    auth_provider: OrganizationAuthProvider | None = None
    is_active: bool | None = None
