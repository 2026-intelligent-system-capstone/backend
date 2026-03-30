from pydantic import BaseModel, Field

class MaterialIngestRequest(BaseModel):
    subject: str = Field(..., description="과목명 (예: 소프트웨어 설계 패턴)")
    week: int = Field(..., description="강의 주차")
    professor: str = Field(..., description="담당 교수명")
    file_path: str = Field(..., description="서버 내 PDF 파일 경로 또는 URL")
    description: str = Field(None, description="자료에 대한 간단한 설명")