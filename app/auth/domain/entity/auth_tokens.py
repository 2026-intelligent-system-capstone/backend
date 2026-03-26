from dataclasses import dataclass


@dataclass(frozen=True)
class AuthTokens:
    user_id: str
    organization_id: str
    organization_code: str
    role: str
    access_token: str
    refresh_token: str
