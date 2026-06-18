import pytest

from app.core.config import Settings
from app.integrations.dashscope import (
    FakeDashScopeClient,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderResponseError,
    ProviderTimeoutError,
    create_dashscope_client,
    normalize_provider_error,
)
from app.integrations.milvus import FakeMilvusClient, MilvusVector, RealMilvusClient, create_milvus_client


def test_dashscope_fake_chat_and_embedding_return_internal_shapes() -> None:
    client = FakeDashScopeClient(
        chat_answer="Use the approved source.",
        embedding=[0.1, 0.2, 0.3],
        embedding_model="fake-embedding",
    )

    answer = client.generate_answer(question="How should I greet a customer?", contexts=[{"text": "Say hello."}])
    embedding = client.embed_text("Say hello.")

    assert answer.answer_text == "Use the approved source."
    assert answer.usage["prompt_tokens"] > 0
    assert not hasattr(answer, "raw_response")
    assert embedding.vector == [0.1, 0.2, 0.3]
    assert embedding.model == "fake-embedding"


def test_dashscope_api_key_is_required_only_for_real_provider_mode() -> None:
    fake_settings = Settings(dashscope_api_key="", use_fake_external_clients=True)
    real_settings = Settings(dashscope_api_key="", use_fake_external_clients=False)

    assert isinstance(create_dashscope_client(fake_settings), FakeDashScopeClient)
    with pytest.raises(ProviderConfigurationError):
        create_dashscope_client(real_settings)


def test_provider_errors_are_standardized() -> None:
    assert normalize_provider_error(TimeoutError()).code == "provider_timeout"
    assert normalize_provider_error(ProviderAuthenticationError("bad key")).code == "provider_authentication_failed"
    assert normalize_provider_error(ValueError("bad payload")).code == "provider_response_invalid"
    assert normalize_provider_error(ProviderTimeoutError("slow")).code == "provider_timeout"
    assert normalize_provider_error(ProviderResponseError("bad shape")).code == "provider_response_invalid"


def test_fake_milvus_collection_schema_upsert_search_and_deactivate() -> None:
    client = FakeMilvusClient()
    client.ensure_collection("weview_scripts", dimension=3)

    schema = client.collections["weview_scripts"]
    assert schema["dimension"] == 3
    assert schema["primary_key"] == "milvus_primary_key"
    assert {"content_id", "version_id", "chunk_id", "permission_level", "is_active"} <= set(schema["metadata_fields"])

    client.upsert_vectors(
        "weview_scripts",
        [
            MilvusVector(
                primary_key="general-1",
                vector=[0.1, 0.2, 0.3],
                metadata={
                    "content_id": 1,
                    "version_id": 1,
                    "chunk_id": 1,
                    "permission_level": "general",
                    "is_active": True,
                },
            ),
            MilvusVector(
                primary_key="full-1",
                vector=[0.2, 0.3, 0.4],
                metadata={
                    "content_id": 2,
                    "version_id": 2,
                    "chunk_id": 2,
                    "permission_level": "full",
                    "is_active": True,
                },
            ),
        ],
    )

    results = client.search(
        "weview_scripts",
        query_vector=[0.1, 0.2, 0.3],
        allowed_permission_levels={"general"},
        top_k=10,
    )
    assert [hit.primary_key for hit in results] == ["general-1"]
    assert client.search_requests[-1].allowed_permission_levels == {"general"}

    client.deactivate_by_content("weview_scripts", content_id=1)
    assert (
        client.search(
            "weview_scripts",
            query_vector=[0.1, 0.2, 0.3],
            allowed_permission_levels={"general"},
            top_k=10,
        )
        == []
    )


def test_milvus_factory_uses_real_client_only_when_fake_clients_are_disabled() -> None:
    fake_settings = Settings(use_fake_external_clients=True)
    real_settings = Settings(use_fake_external_clients=False, milvus_host="127.0.0.1", milvus_port=19530)

    assert isinstance(create_milvus_client(fake_settings), FakeMilvusClient)
    real_client = create_milvus_client(real_settings)
    assert isinstance(real_client, RealMilvusClient)
    assert real_client.host == "127.0.0.1"
    assert real_client.port == 19530
