from fastapi import Depends
from starlette.requests import HTTPConnection

from twin.api.repository import Repository
from twin.common.config import Settings, get_settings


def get_repository(connection: HTTPConnection) -> Repository:
    return connection.app.state.repository


def settings_dependency() -> Settings:
    return get_settings()


RepositoryDep = Depends(get_repository)
SettingsDep = Depends(settings_dependency)
