from dependency_injector import containers, providers
from dependency_injector.containers import DeclarativeContainer

from app.auth.container import AuthContainer
from app.classroom.container import ClassroomContainer
from app.exam.container import ExamContainer
from app.file.container import FileContainer
from app.organization.container import OrganizationContainer
from app.user.container import UserContainer
from app.conversational_evaluation.container import ConversationalEvaluationContainer
from app.learning_material.container import LearningMaterialContainer

class AppContainer(DeclarativeContainer):
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.auth.adapter.input.api.v1",
            "app.classroom.adapter.input.api.v1",
            "app.exam.adapter.input.api.v1",
            "app.file.adapter.input.api.v1",
            "app.organization.adapter.input.api.v1",
            "app.user.adapter.input.api.v1",
            "app.conversational_evaluation.adapter.input.api.v1",
            "app.learning_material.adapter.input.api.v1",
        ]
    )

    auth = providers.Container(AuthContainer)
    classroom = providers.Container(ClassroomContainer)
    exam = providers.Container(ExamContainer)
    file = providers.Container(FileContainer)
    organization = providers.Container(OrganizationContainer)
    user = providers.Container(UserContainer)
    evaluation = providers.Container(ConversationalEvaluationContainer)
    learning_material = providers.Container(LearningMaterialContainer)
