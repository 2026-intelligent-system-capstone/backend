from dependency_injector import containers, providers

from app.classroom.container import ClassroomContainer
from app.exam.adapter.output.integration import (
    LLMExamQuestionGenerationAdapter,
    OpenAIRealtimeSessionAdapter,
)
from app.exam.adapter.output.persistence.sqlalchemy import (
    ExamResultSQLAlchemyRepository,
    ExamSessionSQLAlchemyRepository,
    ExamSQLAlchemyRepository,
    ExamTurnSQLAlchemyRepository,
)
from app.exam.application.service import ExamService


class ExamContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["app.exam.adapter.input.api.v1.exam"]
    )

    repository = providers.Singleton(ExamSQLAlchemyRepository)
    session_repository = providers.Singleton(ExamSessionSQLAlchemyRepository)
    result_repository = providers.Singleton(ExamResultSQLAlchemyRepository)
    turn_repository = providers.Singleton(ExamTurnSQLAlchemyRepository)
    realtime_session_port = providers.Singleton(OpenAIRealtimeSessionAdapter)
    question_generation_port = providers.Singleton(
        LLMExamQuestionGenerationAdapter
    )
    service = providers.Factory(
        ExamService,
        repository=repository,
        classroom_usecase=ClassroomContainer.service,
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=turn_repository,
        realtime_session_port=realtime_session_port,
        question_generation_port=question_generation_port,
    )
