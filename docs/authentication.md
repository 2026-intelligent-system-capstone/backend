# Authentication

## Strategy

This boilerplate uses JWT cookie authentication.

- Access token: short-lived
- Refresh token: long-lived
- Both are returned as `HttpOnly` cookies

## Built-In Endpoints

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`

## Token Storage

Refresh tokens are persisted in Valkey.

Key format:

```text
auth:user:{user_id}:refresh:{jti}
```

## Flow

### Login

1. Validate credentials against the user repository
2. Issue access token
3. Issue refresh token with `jti`
4. Store refresh token in Valkey
5. Set both cookies on the response

### Refresh

1. Read refresh token from cookie
2. Decode and validate token type
3. Resolve `user_id` and `jti`
4. Verify token exists in Valkey
5. Delete previous token
6. Issue new access and refresh tokens
7. Store the new refresh token
8. Replace cookies

### Logout

1. Read refresh token from cookie
2. Resolve `user_id` and `jti` if possible
3. Delete the stored refresh token if present
4. Clear auth cookies

## Security Settings

Relevant env vars:

- `ACCESS_TOKEN_SECRET_KEY`
- `REFRESH_TOKEN_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_MINUTES`
- `ACCESS_TOKEN_COOKIE_NAME`
- `REFRESH_TOKEN_COOKIE_NAME`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`

## Production Checklist

- replace default secret keys
- set `AUTH_COOKIE_SECURE=true`
- review `AUTH_COOKIE_SAMESITE`
- configure trusted frontend origins
- use managed PostgreSQL and Valkey instances
