from dependency_injector import containers, providers
from dependency_injector.containers import DeclarativeContainer

from app.auth.container import AuthContainer
from app.classroom.container import ClassroomContainer
from app.classroom_material.container import ClassroomMaterialContainer
from app.exam.container import ExamContainer
from app.file.container import FileContainer
from app.organization.container import OrganizationContainer
from app.user.container import UserContainer


class AppContainer(DeclarativeContainer):
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.auth.adapter.input.api.v1",
            "app.classroom.adapter.input.api.v1",
            "app.classroom_material.adapter.input.api.v1",
            "app.exam.adapter.input.api.v1",
            "app.file.adapter.input.api.v1",
            "app.organization.adapter.input.api.v1",
            "app.user.adapter.input.api.v1",
        ]
    )

    auth = providers.Container(AuthContainer)
    classroom = providers.Container(ClassroomContainer)
    classroom_material = providers.Container(ClassroomMaterialContainer)
    exam = providers.Container(ExamContainer)
    file = providers.Container(FileContainer)
    organization = providers.Container(OrganizationContainer)
    user = providers.Container(UserContainer)
