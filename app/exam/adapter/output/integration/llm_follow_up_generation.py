from app.exam.domain.service import (
    ExamFollowUpGenerationPort,
    ExamFollowUpGenerationRequest,
    ExamFollowUpGenerationResult,
)


class LLMExamFollowUpGenerationAdapter(ExamFollowUpGenerationPort):
    async def generate_follow_up(
        self,
        *,
        request: ExamFollowUpGenerationRequest,
    ) -> ExamFollowUpGenerationResult:
        _ = request
        return ExamFollowUpGenerationResult(
            content="답변의 근거를 한 단계 더 구체적인 예시로 설명해 주세요.",
            metadata={"augmentation_used": "false"},
        )
