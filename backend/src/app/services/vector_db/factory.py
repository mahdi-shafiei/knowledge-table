"""The factory for the vector database services."""

import logging
from typing import Optional

from app.services.llm.base import LLMService
from app.services.vector_db.base import VectorDBService
from app.services.vector_db.milvus_service import MilvusService
from app.services.vector_db.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


class VectorDBFactory:
    """The factory for the vector database services."""

    @staticmethod
    def create_vector_db_service(
        provider: str, llm_service: LLMService
    ) -> Optional[VectorDBService]:
        """Create the vector database service."""
        logger.info(
            f"Creating vector database service with provider: {provider}"
        )
        provider = provider.lower()
        if provider == "milvus-lite":
            return MilvusService(llm_service)
        elif provider == "qdrant":
            return QdrantService(llm_service)
        # Add other vector database providers here
        logger.warning(f"Unsupported vector database provider: {provider}")
        return None
