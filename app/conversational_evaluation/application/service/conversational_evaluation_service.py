from app.conversational_evaluation.adapter.output.llm.openai_adapter import OpenAIAdapter
from app.learning_material.adapter.output.vector_db.qdrant_adapter import QdrantAdapter
from app.conversational_evaluation.domain.prompt.evaluation_prompts import EXAM_EVALUATOR_SYSTEM_PROMPT
from app.conversational_evaluation.adapter.input.api.v1.request.evaluation_request import EvaluationRequest
from app.conversational_evaluation.adapter.input.api.v1.response.evaluation_result_response import EvaluationResultResponse

class ConversationalEvaluationService:
    def __init__(self, ai_adapter: OpenAIAdapter, qdrant_adapter: QdrantAdapter):
        self.ai_adapter = ai_adapter
        self.qdrant_adapter = qdrant_adapter

    async def evaluate_answer(self, request_dto: EvaluationRequest) -> EvaluationResultResponse:
        # 1. 관련 지식 검색 (RAG)
        docs = await self.qdrant_adapter.search_relevant_docs(
            query=request_dto.student_answer,
            subject=request_dto.context_subject
        )
        context_text = "\n".join([doc.page_content for doc in docs])

        # 2. 평가 프롬프트 구성
        prompt = f"""
        [참고 자료]
        {context_text}

        [학생 답변]
        {request_dto.student_answer}

        위 자료를 바탕으로 학생의 답변을 평가해줘. 
        만약 답변이 완벽하면 'PASS'와 피드백을 주고, 
        부족하거나 모호하면 'FOLLOW_UP'과 함께 구체적인 꼬리 질문을 던져줘.
        """

        # 3. AI 판단 요청
        # (여기서는 단순 텍스트 응답 예시입니다. 나중에 DTO로 구조화 가능)
        response = await self.ai_adapter.generate_structured_output(
            prompt=f"{EXAM_EVALUATOR_SYSTEM_PROMPT}\n\n{prompt}",
            response_model=EvaluationResultResponse # 규격 지정!
        )
        
        return response