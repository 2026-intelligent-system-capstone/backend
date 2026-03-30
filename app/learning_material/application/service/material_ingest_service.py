from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.learning_material.adapter.output.vector_db.qdrant_adapter import QdrantAdapter

class MaterialIngestService:
    def __init__(self, qdrant_adapter: QdrantAdapter):
        self.qdrant_adapter = qdrant_adapter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )

    async def ingest_pdf(self, request_dto):
        # 1. PDF 로드
        loader = PyMuPDFLoader(request_dto.file_path)
        docs = loader.load()
        
        # 2. 메타데이터 추가 (나중에 검색할 때 중요!)
        for doc in docs:
            doc.metadata.update({
                "subject": request_dto.subject,
                "week": request_dto.week,
                "professor": request_dto.professor
            })
            
        # 3. 텍스트 분할 (Chunking)
        chunks = self.text_splitter.split_documents(docs)
        
        # 4. 벡터 DB 저장
        await self.qdrant_adapter.save_documents(chunks)
        
        return {"status": "success", "chunks_count": len(chunks)}