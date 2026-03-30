# app/conversational_evaluation/application/service/exam_generation_service.py

from app.conversational_evaluation.adapter.output.llm.openai_adapter import OpenAIAdapter
from app.conversational_evaluation.adapter.input.api.v1.response.exam_generation_response import ExamGenerationResponse
from app.conversational_evaluation.domain.prompt.evaluation_prompts import EXAM_GENERATOR_SYSTEM_PROMPT

class ExamGenerationService:
    def __init__(self, ai_adapter: OpenAIAdapter):
        self.ai_adapter = ai_adapter

    async def generate_exam(self, request_dto) -> ExamGenerationResponse:
        # 1. 프롬프트 조립 (과목, 범위, 난이도 등 주입) [cite: 311]
        user_prompt = f"""
        과목: {request_dto.subject}
        범위: {request_dto.scope}
        난이도: {request_dto.difficulty}
        문제 수: {request_dto.total_questions}
        Bloom 비율: {request_dto.bloom_ratio}
        
        위 조건에 맞는 문제를 생성해줘.
        """
        
        full_prompt = f"{EXAM_GENERATOR_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        # 2. AI 어댑터 호출 (구조화된 출력 요청) [cite: 280]
        response = await self.ai_adapter.generate_structured_output(
            prompt=full_prompt,
            response_model=ExamGenerationResponse
        )
        
        return response