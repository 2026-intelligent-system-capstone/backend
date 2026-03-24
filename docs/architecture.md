# Architecture

## Overview

Dialearn backend is built around hexagonal architecture.

The primary goal is to keep business logic isolated from framework and persistence details.

## Layer Responsibilities

### Domain

- `command/`: use-case input models
- `entity/`: domain entities and value objects
- `repository/`: repository ports
- `usecase/`: use-case interfaces

Domain code should not depend on FastAPI, SQLAlchemy session objects, or transport details.

### Application

- `service/`: use-case implementations
- `exception/`: application-level business exceptions
- `dto/`: shared result models only when needed

Application services should depend on domain ports directly.

### Adapter Input

- HTTP request schemas
- HTTP response schemas
- routers

Routers translate `Request -> Command`, invoke a use case, and translate the result into response payloads.

### Adapter Output

- SQLAlchemy repositories
- Valkey repositories
- any external system integrations

Output adapters implement domain repository ports.

## Dependency Direction

Allowed direction:

```text
adapter -> application -> domain
adapter -> domain
application -> domain
```

Disallowed direction:

```text
domain -> application
domain -> adapter
application -> adapter/input
application -> adapter wrapper classes
```

## Current Built-In Modules

- `user`
- `auth`
- `file`

These are currently the baseline modules in the backend and will be expanded as Dialearn domain modules are added.

## Persistence Rule

Services use domain ports such as:

- `UserRepository`
- `FileRepository`
- `AuthTokenRepository`

Concrete adapters such as SQLAlchemy or Valkey implementations are wired in containers.

## Request / Response Rule

- request schemas live in `adapter/input/api/v1/request/__init__.py`
- response schemas live in `adapter/input/api/v1/response/__init__.py`
- commands live in `domain/command/__init__.py`

## Testing Rule

Each domain should normally include:

- domain tests
- application/service tests
- API tests
- persistence tests where repository behavior matters
