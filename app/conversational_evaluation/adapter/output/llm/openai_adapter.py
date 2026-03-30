from langchain_openai import ChatOpenAI
from core.config import config  # 백엔드의 설정 파일 로드

class OpenAIAdapter:
    def __init__(self):
        # OpenAI 채팅 모델 초기화
        self.llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            model="gpt-4o", # 혹은 팀에서 사용하는 모델명
            temperature=0.7
        )

    async def generate_structured_output(self, prompt: str, response_model):
        """
        프롬프트를 받아 지정된 Pydantic 모델(DTO) 형태로 구조화된 응답을 반환합니다.
        """
        structured_llm = self.llm.with_structured_output(response_model)
        return await structured_llm.ainvoke(prompt)