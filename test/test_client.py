import pytest
from aiomothr import AsyncMothrClient
from asynctest import CoroutineMock, MagicMock, patch


class TestClient:
    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.mutate", new_callable=CoroutineMock)
    async def test_login(self, mock_mutate):
        mock_mutate.return_value = {
            "login": {"token": "access-token", "refresh": "refresh-token"}
        }
        client = AsyncMothrClient()
        access, refresh = await client.login(username="test", password="password")
        assert access == "access-token"
        assert refresh == "refresh-token"

    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.mutate", new_callable=CoroutineMock)
    async def test_refresh(self, mock_mutate):
        mock_mutate.side_effect = [
            {"login": {"token": "access-token", "refresh": "refresh-token"}},
            {"refresh": {"token": "refreshed-access-token"}},
        ]
        client = AsyncMothrClient()
        await client.login(username="test", password="password")
        access = await client.refresh_token()
        assert access == "refreshed-access-token"

    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.query", new_callable=CoroutineMock)
    async def test_service(self, mock_query):
        mock_query.return_value = {
            "service": [
                {
                    "name": "test",
                    "version": "latest",
                    "parameters": [{"name": "param1", "fileType": {"name": "text"}}],
                },
                {
                    "name": "test",
                    "version": "dev",
                    "parameters": [{"name": "param1", "fileType": {"name": "text"}}],
                },
            ]
        }
        client = AsyncMothrClient()
        service = await client.service(
            name="test",
            fields=["name", "version", "parameters.name", "parameters.fileType.name"],
        )
        assert len(service) == 2

    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.query", new_callable=CoroutineMock)
    async def test_services(self, mock_query):
        mock_query.return_value = {
            "services": [
                {"name": "test-service", "version": "latest"},
                {"name": "test-service", "version": "dev"},
                {"name": "test-service2", "version": "latest"},
                {"name": "test-service2", "version": "dev"},
            ]
        }
        client = AsyncMothrClient()
        services = await client.services()
        assert len(services) == 4
