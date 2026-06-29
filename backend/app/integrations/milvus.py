from dataclasses import dataclass, field
from math import sqrt
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
    visible_department_id: int | None
    include_all_department_scoped: bool
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
                "scope_type",
                "department_id",
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
        visible_department_id: int | None = None,
        include_all_department_scoped: bool = False,
    ) -> list[MilvusSearchHit]:
        self.search_requests.append(
            MilvusSearchRequest(
                collection_name=collection_name,
                query_vector=query_vector,
                allowed_permission_levels=set(allowed_permission_levels),
                visible_department_id=visible_department_id,
                include_all_department_scoped=include_all_department_scoped,
                top_k=top_k,
            )
        )
        if self.search_results is not None:
            candidates = self.search_results
        else:
            candidates = [
                MilvusSearchHit(
                    primary_key=vector.primary_key,
                    score=self._cosine_similarity(query_vector, vector.vector),
                    metadata=vector.metadata,
                )
                for vector in self.vectors.get(collection_name, [])
            ]
        filtered = [
            hit
            for hit in candidates
            if hit.metadata.get("is_active", True)
            and hit.metadata.get("permission_level") in allowed_permission_levels
            and (
                include_all_department_scoped
                or hit.metadata.get("scope_type", "global") == "global"
                or (
                    hit.metadata.get("scope_type") == "department"
                    and visible_department_id is not None
                    and hit.metadata.get("department_id") == visible_department_id
                )
            )
        ]
        return sorted(filtered, key=lambda hit: hit.score, reverse=True)[:top_k]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)

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
    _LEGACY_FIELD_NAMES = {
        "milvus_primary_key",
        "vector",
        "content_id",
        "version_id",
        "chunk_id",
        "permission_level",
        "content_status",
        "is_active",
        "effective_at",
        "expired_at",
    }
    _SCOPE_FIELD_NAMES = {"scope_type", "department_id"}

    def __init__(self, *, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.uri = f"http://{host}:{port}"
        from pymilvus import MilvusClient

        self.client = MilvusClient(uri=self.uri)
        self._field_cache: dict[str, set[str]] = {}

    def ensure_collection(self, collection_name: str, *, dimension: int) -> None:
        from pymilvus import DataType, MilvusClient

        if self.client.has_collection(collection_name):
            self._collection_field_names(collection_name)
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("milvus_primary_key", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field("content_id", DataType.INT64)
        schema.add_field("version_id", DataType.INT64)
        schema.add_field("chunk_id", DataType.INT64)
        schema.add_field("permission_level", DataType.VARCHAR, max_length=32)
        schema.add_field("scope_type", DataType.VARCHAR, max_length=32)
        schema.add_field("department_id", DataType.INT64, nullable=True)
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
        self._field_cache[collection_name] = self._LEGACY_FIELD_NAMES | self._SCOPE_FIELD_NAMES

    def upsert_vectors(self, collection_name: str, vectors: list[MilvusVector]) -> None:
        field_names = self._collection_field_names(collection_name)
        data = [
            {
                "milvus_primary_key": vector.primary_key,
                "vector": vector.vector,
                **self._metadata_supported_by_schema(vector.metadata, field_names),
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
        visible_department_id: int | None = None,
        include_all_department_scoped: bool = False,
    ) -> list[MilvusSearchHit]:
        field_names = self._collection_field_names(collection_name)
        quoted_levels = ", ".join(f'"{level}"' for level in sorted(allowed_permission_levels))
        if include_all_department_scoped or not self._schema_supports_scope_filter(field_names):
            scope_filter = ""
        elif visible_department_id is None:
            scope_filter = ' and scope_type == "global"'
        else:
            scope_filter = (
                f' and (scope_type == "global" '
                f'or (scope_type == "department" and department_id == {visible_department_id}))'
            )
        filter_expr = f"is_active == true and permission_level in [{quoted_levels}]{scope_filter}"
        output_fields = [
            field_name
            for field_name in [
                "content_id",
                "version_id",
                "chunk_id",
                "permission_level",
                "scope_type",
                "department_id",
                "content_status",
                "is_active",
                "effective_at",
                "expired_at",
                "milvus_primary_key",
            ]
            if field_name in field_names
        ]
        results = self.client.search(
            collection_name=collection_name,
            data=[query_vector],
            filter=filter_expr,
            limit=top_k,
            output_fields=output_fields,
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

    def _collection_field_names(self, collection_name: str) -> set[str]:
        if collection_name in self._field_cache:
            return self._field_cache[collection_name]
        if not self.client.has_collection(collection_name):
            self._field_cache[collection_name] = self._LEGACY_FIELD_NAMES | self._SCOPE_FIELD_NAMES
            return self._field_cache[collection_name]
        try:
            try:
                description = self.client.describe_collection(collection_name=collection_name)
            except TypeError:
                description = self.client.describe_collection(collection_name)
            raw_fields = description.get("fields", []) if isinstance(description, dict) else []
            field_names: set[str] = set()
            for field in raw_fields:
                if isinstance(field, dict):
                    field_name = field.get("name") or field.get("field_name")
                else:
                    field_name = getattr(field, "name", None)
                if field_name:
                    field_names.add(str(field_name))
        except Exception:
            field_names = set(self._LEGACY_FIELD_NAMES)
        if not field_names:
            field_names = set(self._LEGACY_FIELD_NAMES)
        self._field_cache[collection_name] = field_names
        return field_names

    def _metadata_supported_by_schema(self, metadata: dict, field_names: set[str]) -> dict:
        return {key: value for key, value in metadata.items() if key in field_names}

    def _schema_supports_scope_filter(self, field_names: set[str]) -> bool:
        return self._SCOPE_FIELD_NAMES <= field_names


def create_milvus_client(settings: Settings | None = None) -> FakeMilvusClient | RealMilvusClient:
    resolved_settings = settings or Settings()
    if resolved_settings.use_fake_external_clients:
        return FakeMilvusClient()
    return RealMilvusClient(host=resolved_settings.milvus_host, port=resolved_settings.milvus_port)
