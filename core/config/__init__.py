import os
from enum import StrEnum
from functools import lru_cache

from .base import CommonSettings
from .dev import DevSettings
from .local import LocalSettings
from .prod import ProdSettings
from .test import TestSettings

Config = CommonSettings


class Env(StrEnum):
    prod = "prod"
    dev = "dev"
    local = "local"
    test = "test"


def get_env() -> Env:
    value = os.getenv("ENVIRONMENT") or os.getenv("ENV") or Env.local.value
    return Env(value)


@lru_cache
def get_settings() -> CommonSettings:
    match get_env():
        case Env.prod:
            return ProdSettings()
        case Env.dev:
            return DevSettings()
        case Env.test:
            return TestSettings()
        case _:
            return LocalSettings()


config = get_settings()
