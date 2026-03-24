from fastapi import FastAPI

from core.config import Config, Env


class ExtendedFastAPI(FastAPI):
    def __init__(self, env: Env, settings: Config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env = env
        self.settings = settings
