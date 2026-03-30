from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from core.config import config

class QdrantAdapter:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY)
        self.client = QdrantClient(url=config.QDRANT_URL)
        self.collection_name = config.QDRANT_COLLECTION_NAME

    async def save_documents(self, documents):
        """문서 청크들을 Qdrant에 벡터화하여 저장합니다."""
        # LangChain의 Qdrant 클래스는 동기 방식으로 동작하므로 래핑하여 사용
        return QdrantVectorStore.from_documents(
            documents=documents,
            embedding=self.embeddings,
            url=config.QDRANT_URL,
            collection_name=self.collection_name,
        )
    async def search_relevant_docs(self, query: str, subject: str, top_k: int = 3):
        """질문과 관련된 PDF 본문을 검색합니다."""
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embeddings=self.embeddings,
        )
        # 과목명으로 필터링하여 검색
        return vector_store.similarity_search(
            query=query,
            k=top_k,
            filter={"subject": subject}
        )