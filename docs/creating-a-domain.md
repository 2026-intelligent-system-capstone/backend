# Creating a Domain

Use the built-in `user`, `auth`, and `file` modules as the reference implementation.

## Recommended Structure

```text
app/<domain>/
  domain/
    command/
      __init__.py
    entity/
      <domain>.py
    repository/
      <domain>.py
    usecase/
      <domain>.py
  application/
    exception/
      <domain>.py
    service/
      <domain>.py
  adapter/
    input/
      api/v1/
        request/
          __init__.py
        response/
          __init__.py
        <domain>.py
    output/
      persistence/
        sqlalchemy/
          <domain>.py
  container.py
```

## Build Order

1. Create domain entity
2. Create command models
3. Define repository port
4. Define use-case interface
5. Implement application service
6. Implement request/response schemas
7. Add router
8. Implement output persistence adapter
9. Wire container
10. Add tests

## Naming

- request: `CreateThingRequest`, `UpdateThingRequest`
- command: `CreateThingCommand`, `UpdateThingCommand`
- payload: `ThingPayload`
- response envelope: `ThingResponse`, `ThingListResponse`
- use case: `ThingUseCase`
- repository port: `ThingRepository`

## Rules

- routers build commands from request models
- services depend on repository ports directly
- persistence adapters implement repository ports
- keep response payload construction in the router when mapping is simple
- add `application/dto/result.py` only when a dedicated read model is justified

## Minimum Tests

- `tests/app/<domain>/domain/test_<domain>_entity.py`
- `tests/app/<domain>/application/test_<domain>_service.py`
- `tests/app/<domain>/adapter/input/test_<domain>_api.py`

Add persistence tests when repository behavior is important.
