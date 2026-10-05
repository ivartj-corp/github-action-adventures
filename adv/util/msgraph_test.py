import os
import asyncio

import pytest
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential
from .msgraph import MsGraphClient


@pytest.fixture
def token_credential() -> AsyncTokenCredential:
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    match tenant_id, client_id:
        case (None, _) | (_, None):
            raise Exception("AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables must be set")
        case _, _:
            pass
    token_credential = DefaultAzureCredential(
        authority="https://login.microsoftonline.com/f8edff44-22a3-4b56-952d-e7012e1a6a0a",
    )
    return token_credential


@pytest.mark.skipif(
    os.environ.get("RUN_MSGRAPH_INTEGRATION_TESTS") is None,
    reason="RUN_MSGRAPH_INTEGEGRATION_TESTS not set",
)
def test_basic(token_credential: AsyncTokenCredential) -> None:
    async def inner() -> None:
        async with MsGraphClient(token_credential) as msgraph:
            async for application in msgraph.applications.list():
                pass
    asyncio.run(inner())

    
