from dependency_injector import containers, providers
from app.learning_material.adapter.output.vector_db.qdrant_adapter import QdrantAdapter
from app.learning_material.application.service.material_ingest_service import MaterialIngestService

class LearningMaterialContainer(containers.DeclarativeContainer):
    # 1. 아웃풋 어댑터 (Qdrant 연결)
    qdrant_adapter = providers.Singleton(QdrantAdapter)

    # 2. 애플리케이션 서비스 (비즈니스 로직)
    material_ingest_service = providers.Factory(
        MaterialIngestService,
        qdrant_adapter=qdrant_adapter
    )
    
LearningMaterialContainer().wire(
    modules=[
        "app.learning_material.adapter.input.api.v1.learning_material_api",
    ]
)