import functools
from types import TracebackType
import typing
import collections.abc
from urllib.parse import quote

import aiohttp
from azure.core.credentials_async import AsyncTokenCredential


MSGRAPH_SCOPE = "https://graph.microsoft.com/.default"


class MsGraphClient:
    _client: aiohttp.ClientSession

    def __init__(
            self,
            credential: AsyncTokenCredential,
            base_url: str = "https://graph.microsoft.com/v1.0/",
    ) -> None:
        async def auth_middleware(
                req: aiohttp.ClientRequest,
                handler: aiohttp.ClientHandlerType,
        ) -> aiohttp.ClientResponse:
            token, _ = await credential.get_token(MSGRAPH_SCOPE)
            req.headers.add(
                "Authorization",
                f"Bearer {token}",
            )
            return await handler(req)

        self._client = aiohttp.ClientSession(
            base_url=base_url,
            middlewares=(auth_middleware,),
        )

    async def __aenter__(self) -> typing.Self:
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        await self._client.__aexit__(
            exc_type,
            exc_val,
            exc_tb,
        )

    @functools.cached_property
    def groups(self) -> GroupRepository:
        return GroupRepository(self._client)

    @functools.cached_property
    def applications(self) -> ApplicationRepository:
        return ApplicationRepository(self._client)

    @functools.cached_property
    def service_principals(self) -> ServicePrincipalRepository:
        return ServicePrincipalRepository(self._client)


class MsGraphException(Exception):
    _status: int
    _code: str | None
    _message: str | None
    _inner_error: "MsGraphException | None"
    _details: list["MsGraphException"]

    def __init__(
            self,
            status: int,
            message: str | None = None,
            error_object: object | None = None,
            when: str | None = None,
    ) -> None:
        self._status = status
        self._code = None
        self._message = None
        self._inner_error = None
        self._details = []

        match status >= 400, message, when:
            case True, None, _:
                pass
            case False, None, None:
                BaseException.__init__(self, f"unexpected HTTP status code {self._status}")
            case False, None, str():
                BaseException.__init__(self, f"unexpected HTTP status code {self._status} (when {when})")
            case False, str(), None:
                BaseException.__init__(self, message)
                return
            case False, str(), str():
                BaseException.__init__(self, f"{message} (when {when})")
                return
            case True, str(), None:
                BaseException.__init__(self, f"HTTP status {status}: {message}")
                return
            case True, str(), str():
                BaseException.__init__(self, f"HTTP status {status}: {message} (when {when})")
                return

        if not isinstance(error_object, dict):
            BaseException.__init__(self, f"unexpected HTTP status code {self._status}, response is in not the expected error format")
            return

        code, message = error_object.get("code"), error_object.get("message")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        match code, message:
            case str(), str():
                self._code = code
                self._message = message
            case _:  # pyright: ignore[reportUnknownVariableType]
                pass

        if (inner_error := error_object.get("innererror")) is not None:  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            self._inner_error = MsGraphException(status, error_object=typing.cast(object, inner_error))
            self.__cause__ = self._inner_error  # pyright: ignore[reportUnannotatedClassAttribute]

        if isinstance(details := error_object.get("details"), list):  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            self._details = [MsGraphException(status, error_object=typing.cast(object, detail)) for detail in details]  # pyright: ignore[reportUnknownVariableType]

        if when is not None:
            BaseException.__init__(self, f"unexpected HTTP status code {self._status} when {when}, Microsoft Graph error code {self._code}: {self._message}")
        else:
            BaseException.__init__(self, f"unexpected HTTP status code {self._status}, Microsoft Graph error code {self._code}: {self._message}")

    @classmethod
    async def from_response(
            cls,
            response: aiohttp.ClientResponse,
            when: str | None = None,
    ) -> MsGraphException:
        json_object: object | None = None
        error_object: object | None = None
        try:
            json_object = typing.cast(object | None, await response.json())
            if isinstance(json_object, dict):
                error_object = typing.cast(object | None, json_object.get("error"))  # pyright: ignore[reportUnknownMemberType]
        except Exception:
            pass
        return cls(
            status=response.status,
            error_object=error_object,
            when=when,
        )


CreateClass = typing.TypeVar("CreateClass")
GetClass = typing.TypeVar("GetClass")


class User(typing.TypedDict):
    id: str
    displayName: str
    userPrincipalName: str


def odata_type_of(resource_type: type[User | Group | Application | ServicePrincipal]) -> str:
    match resource_type:
        case x if x is User:
            return "microsoft.graph.user"
        case x if x is Group:
            return "microsoft.graph.group"
        case x if x is Application:
            return "microsoft.graph.application"
        case x if x is ServicePrincipal:
            return "microsoft.graph.servicePrincipal"
        case _:
            raise Exception(f"unhandled type {resource_type}")


class BaseRepository(typing.Generic[CreateClass, GetClass]):
    _client: aiohttp.ClientSession
    _endpoint: str

    def __init__(
            self,
            client: aiohttp.ClientSession,
            endpoint: str,
    ) -> None:
        self._client = client
        self._endpoint = endpoint

    async def create(self, resource: CreateClass) -> GetClass:
        response = await self._client.post(self._endpoint, json=resource)
        if response.status != 201:
            raise await MsGraphException.from_response(response, when=f"creating a resource on {self._endpoint}")
        return typing.cast(
            GetClass,
            await response.json(),
        )

    async def get(
            self,
            id: str,
    ) -> GetClass | None:
        url = f"{self._endpoint}/{quote(id)}"
        response = await self._client.get(url)
        match response.status:
            case 404:
                return None
            case 200:
                return typing.cast(GetClass, await response.json())
            case _:
                raise await MsGraphException.from_response(response, when=f"getting {url}")

    async def _list_from_pages[T](
            self,
            endpoint: str,
            filter: str | None = None,
            select: tuple[str] | None = None,
            expand: tuple[str] | None = None,
    ) -> collections.abc.AsyncGenerator[T]:
        params: dict[str, str] = {}
        if filter is not None:
            params["$filter"] = filter
        if select is not None:
            params["$select"] = ",".join(select)
        if expand is not None:
            params["$expand"] = ",".join(expand)
        response = await self._client.get(
            url=endpoint,
            params=params,
        )
        while True:
            if response.status != 200:
                raise await MsGraphException.from_response(response, when=f"listing from {endpoint}")
            response_object = typing.cast(object, await response.json())
            if not isinstance(response_object, dict):
                raise MsGraphException(response.status, "failed to parse response", when=f"listing from {endpoint}")
            value = typing.cast(object | None, response_object.get("value"))  # pyright: ignore[reportUnknownMemberType]
            if not isinstance(value, list):
                raise MsGraphException(response.status, "failed to parse response", when=f"listing from {endpoint}")
            for resource in value:  # pyright: ignore[reportUnknownVariableType]
                yield typing.cast(T, resource)
            next_link = typing.cast(object | None, response_object.get("@odata.nextLink"))  # pyright: ignore[reportUnknownMemberType]
            if not isinstance(next_link, str):
                break
            response = await self._client.get(next_link)


    async def list(
            self,
            filter: str | None = None,
            select: tuple[str] | None = None,
            expand: tuple[str] | None = None,
    ) -> collections.abc.AsyncGenerator[GetClass]:
        async for resource in self._list_from_pages(  # pyright: ignore[reportUnknownVariableType]
            endpoint=self._endpoint,
            filter=filter,
            select=select,
            expand=expand,
        ):
            yield resource


    async def update(
            self,
            id: str,
            resource: dict[str, object | None],
    ) -> None:
        url = f"{self._endpoint}/{quote(id)}"
        response = await self._client.patch(url, json=resource)
        match response.status:
            case 204 | 200:
                return None
            case _:
                raise await MsGraphException.from_response(response, when=f"updating {self._endpoint}/{id}")

    async def delete(self, id: str) -> None:
        url = f"{self._endpoint}/{quote(id)}"
        response = await self._client.delete(url)
        match response.status:
            case 204:
                return None
            case _:
                raise await MsGraphException.from_response(response, when=f"deleting {self._endpoint}/{id}")

    async def member_of_groups_direct(
            self,
            id: str,
            filter: str | None = None,
            select: tuple[str] | None = None,
            expand: tuple[str] | None = None,
    ) -> collections.abc.AsyncGenerator[Group]:
        async for resource in self._list_from_pages(  # pyright: ignore[reportUnknownVariableType]
            endpoint=f"{self._endpoint}/{quote(id)}/memberOf/microsoft.graph.group",
            filter=filter,
            select=select,
            expand=expand,
        ):
            yield resource

    async def member_of_groups_all(
            self,
            id: str,
            filter: str | None = None,
            select: tuple[str] | None = None,
            expand: tuple[str] | None = None,
    ) -> collections.abc.AsyncGenerator[Group]:
        async for resource in self._list_from_pages(  # pyright: ignore[reportUnknownVariableType]
            endpoint=f"{self._endpoint}/{quote(id)}/transitiveMemberOf/microsoft.graph.group",
            filter=filter,
            select=select,
            expand=expand,
        ):
            yield resource

    async def list_owners(
            self,
            id: str,
            resource_type: type[User | ServicePrincipal],
            filter: str | None = None,
            select: tuple[str] | None = None,
            expand: tuple[str] | None = None,
    ) -> collections.abc.AsyncGenerator[ServicePrincipal]:
        url = f"{self._endpoint}/{quote(id)}/owners/{odata_type_of(resource_type)}"
        async for resource in self._list_from_pages(  # pyright: ignore[reportUnknownVariableType]
            endpoint=url,
            filter=filter,
            select=select,
            expand=expand,
        ):
            yield resource        


class GroupCreate(typing.TypedDict):
    displayName: str
    mailEnabled: typing.Literal[False]
    mailNickName: str
    securityEnabled: typing.Literal[True]


class Group(GroupCreate):
    id: str


class GroupRepository(BaseRepository[GroupCreate, Group]):
    def __init__(
            self,
            client: aiohttp.ClientSession,
    ) -> None:
        BaseRepository.__init__(self, client, "/v1.0/groups")  # pyright: ignore[reportUnknownMemberType]

    async def list_members_direct[T : User | ServicePrincipal | Group](
            self,
            id: str,
            resource_type: type[T],
            filter: str | None = None,
            select: tuple[str] | None = None,
            expand: tuple[str] | None = None,
    ) -> collections.abc.AsyncGenerator[T]:
        url = f"{self._endpoint}/{quote(id)}/members/{odata_type_of(resource_type)}"
        async for resource in self._list_from_pages(  # pyright: ignore[reportUnknownVariableType]
            endpoint=url,
            filter=filter,
            select=select,
            expand=expand,
        ):
            yield resource        

    async def add_member(
            self,
            group_id: str,
            member_id: str,
    ) -> None:
        url = f"{self._endpoint}/{quote(group_id)}/members/$ref"
        response = await self._client.post(url, json={
            "@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{member_id}",
        })
        if response.status != 204:
            raise await MsGraphException.from_response(response, when=f"adding a member on {url}")

    async def remove_member(
            self,
            group_id: str,
            member_id: str,
    ) -> None:
        url = f"{self._endpoint}/{quote(group_id)}/members/{quote(member_id)}/$ref"
        response = await self._client.delete(url)
        if response.status != 204:
            raise await MsGraphException.from_response(response, when=f"removing a member on {url}")


class ApplicationCreate(typing.TypedDict):
    displayName: str


class Application(ApplicationCreate):
    id: str


class ApplicationRepository(BaseRepository[ApplicationCreate, Application]):
    def __init__(
            self,
            client: aiohttp.ClientSession,
    ) -> None:
        BaseRepository.__init__(self, client, "/v1.0/applications")  # pyright: ignore[reportUnknownMemberType]


class ServicePrincipalCreate(typing.TypedDict):
    appId: str


class ServicePrincipal(ServicePrincipalCreate):
    id: str


class ServicePrincipalRepository(BaseRepository[ServicePrincipalCreate, ServicePrincipal]):
    def __init__(
            self,
            client: aiohttp.ClientSession,
    ) -> None:
        BaseRepository.__init__(self, client, "/v1.0/servicePrincipals")  # pyright: ignore[reportUnknownMemberType]


    # New-MgApplicationExtensionProperty
    # Get-MgApplicationExtensionProperty
    # Get-MgApplication
    # Get-MgServicePrincipal
    # Get-MgGroup
    # Get-MgGroupMemberAsServicePrincipal
    # New-MgGroupMember
    # Update-MgGroup
    # Update-MgApplication
    # Get-MgGroupOwner
    # Get-MgApplicationOwner
    # Remove-MgGroupMemberDirectoryObjectByRef
    # New-MgGroup
    # New-MgApplication
    # New-MgServicePrincipal
    # Add-MgApplicationPassword
    # Remove-MgGroup
    # Remove-MgApplication
