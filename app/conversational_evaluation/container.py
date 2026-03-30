from dependency_injector import containers, providers
from app.conversational_evaluation.adapter.output.llm.openai_adapter import OpenAIAdapter
from app.conversational_evaluation.application.service.exam_generation_service import ExamGenerationService

class ConversationalEvaluationContainer(containers.DeclarativeContainer):
    # 1. 인프라 레이어 (OpenAI 통신 어댑터)
    ai_adapter = providers.Singleton(OpenAIAdapter)

    # 2. 애플리케이션 레이어 (비즈니스 로직 서비스)
    # ai_adapter를 주입(Injection)받도록 설정합니다.
    exam_generation_service = providers.Factory(
        ExamGenerationService,
        ai_adapter=ai_adapter
    )
    
ConversationalEvaluationContainer().wire(
modules=[
    "app.conversational_evaluation.adapter.input.api.v1.conversational_evaluation",
]
)