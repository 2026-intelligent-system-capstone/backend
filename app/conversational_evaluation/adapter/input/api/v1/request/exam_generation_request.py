from pydantic import BaseModel, Field
from typing import Optional

class ExamGenerationRequest(BaseModel):
    subject: str = Field(..., description="과목명 (예: 소프트웨어 설계 패턴)")
    exam_type: str = Field(..., alias="type", description="시험 유형 (quiz, midterm, final)")
    scope: str = Field(..., description="시험 범위 (예: 1-2주차 디자인 패턴 전체)")
    total_questions: int = Field(default=5, alias="total", description="총 문제 수")
    
    # 기획서 및 README의 Bloom's Taxonomy 비율 설정
    bloom_ratio: str = Field(
        default="10:20:20:20:15:15", 
        description="Bloom 단계별 배분 비율 (기억:이해:적용:분석:종합:평가)"
    )
    
    difficulty: str = Field(default="중", description="난이도 (상/중/하)")
    max_followups: int = Field(default=3, description="최대 꼬리질문 허용 수")