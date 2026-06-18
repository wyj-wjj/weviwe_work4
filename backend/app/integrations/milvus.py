from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings


@dataclass(frozen=True)
class MilvusVector:
    primary_key: str
    vector: list[float]
    metadata: dict


@dataclass(frozen=True)
class MilvusSearchHit:
    primary_key: str
    score: float
    metadata: dict


@dataclass(frozen=True)
class MilvusSearchRequest:
    collection_name: str
    query_vector: list[float]
    allowed_permission_levels: set[str]
    top_k: int


class FakeMilvusClient:
    def __init__(self, *, search_results: list[MilvusSearchHit] | None = None) -> None:
        self.collections: dict[str, dict] = {}
        self.vectors: dict[str, list[MilvusVector]] = {}
        self.search_results = search_results
        self.search_requests: list[MilvusSearchRequest] = []
        self.upsert_requests: list[tuple[str, list[MilvusVector]]] = []
        self.deactivate_requests: list[tuple[str, int | None, int | None]] = []

    def ensure_collection(self, collection_name: str, *, dimension: int) -> None:
        self.collections[collection_name] = {
            "dimension": dimension,
            "primary_key": "milvus_primary_key",
            "metadata_fields": [
                "content_id",
                "version_id",
                "chunk_id",
                "permission_level",
                "content_status",
                "is_active",
                "effective_at",
                "expired_at",
            ],
        }
        self.vectors.setdefault(collection_name, [])

    def upsert_vectors(self, collection_name: str, vectors: list[MilvusVector]) -> None:
        self.upsert_requests.append((collection_name, vectors))
        existing = {vector.primary_key: vector for vector in self.vectors.setdefault(collection_name, [])}
        for vector in vectors:
            existing[vector.primary_key] = vector
        self.vectors[collection_name] = list(existing.values())

    def search(
        self,
        collection_name: str,
        *,
        query_vector: list[float],
        allowed_permission_levels: set[str],
        top_k: int,
    ) -> list[MilvusSearchHit]:
        self.search_requests.append(
            MilvusSearchRequest(
                collection_name=collection_name,
                query_vector=query_vector,
                allowed_permission_levels=set(allowed_permission_levels),
                top_k=top_k,
            )
        )
        if self.search_results is not None:
            candidates = self.search_results
        else:
            candidates = [
                MilvusSearchHit(primary_key=vector.primary_key, score=1.0, metadata=vector.metadata)
                for vector in self.vectors.get(collection_name, [])
            ]
        filtered = [
            hit
            for hit in candidates
            if hit.metadata.get("is_active", True)
            and hit.metadata.get("permission_level") in allowed_permission_levels
        ]
        return sorted(filtered, key=lambda hit: hit.score, reverse=True)[:top_k]

    def deactivate_by_content(
        self,
        collection_name: str,
        *,
        content_id: int | None = None,
        version_id: int | None = None,
    ) -> None:
        self.deactivate_requests.append((collection_name, content_id, version_id))
        updated: list[MilvusVector] = []
        for vector in self.vectors.get(collection_name, []):
            metadata = dict(vector.metadata)
            matches_content = content_id is not None and metadata.get("content_id") == content_id
            matches_version = version_id is not None and metadata.get("version_id") == version_id
            if matches_content or matches_version:
                metadata["is_active"] = False
                updated.append(MilvusVector(primary_key=vector.primary_key, vector=vector.vector, metadata=metadata))
            else:
                updated.append(vector)
        self.vectors[collection_name] = updated


class RealMilvusClient:
    def __init__(self, *, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.uri = f"http://{host}:{port}"
        from pymilvus import MilvusClient

        self.client = MilvusClient(uri=self.uri)

    def ensure_collection(self, collection_name: str, *, dimension: int) -> None:
        from pymilvus import DataType, MilvusClient

        if self.client.has_collection(collection_name):
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("milvus_primary_key", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field("content_id", DataType.INT64)
        schema.add_field("version_id", DataType.INT64)
        schema.add_field("chunk_id", DataType.INT64)
        schema.add_field("permission_level", DataType.VARCHAR, max_length=32)
        schema.add_field("content_status", DataType.VARCHAR, max_length=32)
        schema.add_field("is_active", DataType.BOOL)
        schema.add_field("effective_at", DataType.VARCHAR, max_length=64, nullable=True)
        schema.add_field("expired_at", DataType.VARCHAR, max_length=64, nullable=True)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )

    def upsert_vectors(self, collection_name: str, vectors: list[MilvusVector]) -> None:
        data = [
            {
                "milvus_primary_key": vector.primary_key,
                "vector": vector.vector,
                **vector.metadata,
            }
            for vector in vectors
        ]
        if data:
            self.client.upsert(collection_name=collection_name, data=data)
            self.client.flush(collection_name)
            self.client.load_collection(collection_name)

    def search(
        self,
        collection_name: str,
        *,
        query_vector: list[float],
        allowed_permission_levels: set[str],
        top_k: int,
    ) -> list[MilvusSearchHit]:
        quoted_levels = ", ".join(f'"{level}"' for level in sorted(allowed_permission_levels))
        filter_expr = f"is_active == true and permission_level in [{quoted_levels}]"
        results = self.client.search(
            collection_name=collection_name,
            data=[query_vector],
            filter=filter_expr,
            limit=top_k,
            output_fields=[
                "content_id",
                "version_id",
                "chunk_id",
                "permission_level",
                "content_status",
                "is_active",
                "effective_at",
                "expired_at",
                "milvus_primary_key",
            ],
            search_params={"metric_type": "COSINE"},
        )
        hits: list[MilvusSearchHit] = []
        for item in results[0] if results else []:
            entity: dict[str, Any] = item.get("entity", {})
            primary_key = str(item.get("milvus_primary_key") or item.get("id") or entity.get("milvus_primary_key"))
            score = float(item.get("distance", item.get("score", 0.0)))
            hits.append(MilvusSearchHit(primary_key=primary_key, score=score, metadata=entity))
        return hits

    def deactivate_by_content(
        self,
        collection_name: str,
        *,
        content_id: int | None = None,
        version_id: int | None = None,
    ) -> None:
        filters: list[str] = []
        if content_id is not None:
            filters.append(f"content_id == {content_id}")
        if version_id is not None:
            filters.append(f"version_id == {version_id}")
        if not filters or not self.client.has_collection(collection_name):
            return
        self.client.delete(collection_name=collection_name, filter=" and ".join(filters))


def create_milvus_client(settings: Settings | None = None) -> FakeMilvusClient | RealMilvusClient:
    resolved_settings = settings or Settings()
    if resolved_settings.use_fake_external_clients:
        return FakeMilvusClient()
    return RealMilvusClient(host=resolved_settings.milvus_host, port=resolved_settings.milvus_port)
