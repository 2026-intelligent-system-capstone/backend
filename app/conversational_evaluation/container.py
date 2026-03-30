from dependency_injector import containers, providers
from app.conversational_evaluation.adapter.output.llm.openai_adapter import OpenAIAdapter
from app.learning_material.adapter.output.vector_db.qdrant_adapter import QdrantAdapter # 추가
from app.conversational_evaluation.application.service.exam_generation_service import ExamGenerationService
from app.conversational_evaluation.application.service.conversational_evaluation_service import ConversationalEvaluationService # 추가

class ConversationalEvaluationContainer(containers.DeclarativeContainer):
    # 어댑터들
    ai_adapter = providers.Singleton(OpenAIAdapter)
    qdrant_adapter = providers.Singleton(QdrantAdapter) # Qdrant 연결 추가

    # 서비스들
    exam_generation_service = providers.Factory(
        ExamGenerationService,
        ai_adapter=ai_adapter
    )
    
    # [추가] 답변 평가 서비스 등록
    conversational_evaluation_service = providers.Factory(
        ConversationalEvaluationService,
        ai_adapter=ai_adapter,
        qdrant_adapter=qdrant_adapter
    )