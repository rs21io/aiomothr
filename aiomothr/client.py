# Copyright 2020 Resilient Solutions Inc. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from __future__ import annotations
import asyncio
import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

from gql import Client
from gql.dsl import DSLField, DSLSchema, DSLType
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport


with open(
    os.path.join(os.path.realpath(os.path.dirname(__file__)), "schema.graphql")
) as f:
    schema = f.read()


USERNAME_VAR = "MOTHR_USERNAME"
PASSWORD_VAR = "MOTHR_PASSWORD"
URL_VAR = "MOTHR_ENDPOINT"
TOKEN_VAR = "MOTHR_ACCESS_TOKEN"


class AsyncMothrClient:
    """Asynchronous client for connecting to MOTHR

    Args:
        url (str, optional): Endpoint to send the job request,
            checks for ``MOTHR_ENDPOINT`` in environment variables otherwise
            defaults to ``http://localhost:8080/query``
        token (str, optional): Access token to use for authentication, the library
            also looks for ``MOTHR_ACCESS_TOKEN`` in the environment as a fallback
        username (str, optional): Username for logging in, if not given the library
            will attempt to use ``MOTHR_USERNAME`` environment variable. If neither
            are found the request will be made without authentication.
        password (str, optional): Password for logging in, if not given the library
            will attempt to use the ``MOTHR_PASSWORD`` environment variable. If
            neither are found the request will be made without authentication.
    """

    def __init__(self, **kwargs):
        schemes = {"http": "ws", "https": "wss"}
        self.headers: Dict[str, str] = {}
        endpoint = os.getenv(URL_VAR, "http://localhost:8080/query")
        url = kwargs.pop("url", endpoint)
        split_url = urlsplit(url)
        ws_url = urlunsplit(split_url._replace(scheme=schemes[split_url.scheme]))

        self.transport = AIOHTTPTransport(url=url, headers=self.headers)
        self.ws_transport = WebsocketsTransport(url=ws_url)
        self.schema = schema
        self.ds = DSLSchema(Client(schema=self.schema))

        self.token = kwargs.pop("token", os.getenv(TOKEN_VAR))
        username = kwargs.pop("username", os.getenv(USERNAME_VAR))
        password = kwargs.pop("password", os.getenv(PASSWORD_VAR))
        if self.token is not None:
            self.headers = {"Authorization": f"Bearer {self.token}"}
        elif all((username, password)):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.login(username, password))

        # Mapping for nested fields
        self.field_map = {
            "Job": {
                "outputMetadata": self.ds.Metadata,
                "parameters": self.ds.Parameter,
                "user": self.ds.User,
                "worker": self.ds.Worker,
            },
            "Service": {
                "parameters": self.ds.ServiceParameter,
                "fileType": self.ds.FileType,
            },
        }

    async def login(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """Retrieve a web token from MOTHR

        Args:
            username (str, optional): Username used to login, the library will look
                for ``MOTHR_USERNAME`` in the environment as a fallback.
            password (str, optional): Password used to login, the library will look
                for ``MOTHR_PASSWORD`` in the environment as a fallback.

        Returns:
            str: An access token to pass with future requests
            str: A refresh token for receiving a new access token
                after the current token expires

        Raises:
            ValueError: If a username or password are not provided and are not found
                in the current environment
        """
        username = username if username is not None else os.getenv("MOTHR_USERNAME")
        password = password if password is not None else os.getenv("MOTHR_PASSWORD")
        if username is None:
            raise ValueError("Username not provided")
        if password is None:
            raise ValueError("Password not provided")

        credentials = {"username": username, "password": password}
        q = self.ds.Mutation.login.args(**credentials).select(
            self.ds.LoginResponse.token, self.ds.LoginResponse.refresh
        )
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = await ds.mutate(q)
        tokens = resp["login"]
        if tokens is None:
            raise ValueError("Login failed")
        self.token = tokens["token"]
        self.refresh = tokens["refresh"]
        self.headers["Authorization"] = f"Bearer {self.token}"
        return self.token, self.refresh

    async def refresh_token(self) -> str:
        """Refresh an expired access token

        Returns:
            str: New access token
        """
        q = self.ds.Mutation.refresh.args(token=self.refresh)
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = await ds.mutate(q)
        if resp["refresh"] is None:
            raise ValueError("Token refresh failed")
        token = resp["refresh"]["token"]
        self.token = token
        self.headers["Authorization"] = f"Bearer {self.token}"
        return token

    async def service(
        self,
        name: str,
        version: Optional[str] = "*",
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Query a service by name

        Args:
            name (str): Name of the service
            version (str, optional): Version to retrieve.
                If no version is given all versions of the service will be returned.
                Wildcards are also accepted.
            fields (list<str>, optional): Fields to return in the query response,
                default is `name` and `version`

        Returns:
            list<dict>: Service records matching the query
        """
        fields = fields if fields is not None else ["name", "version"]
        fields = [self.resolve_field(self.ds.Service, field) for field in fields]
        q = self.ds.Query.service.args(name=name, version=version).select(*fields)
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = await ds.query(q)
        return resp["service"]

    async def services(self, fields: Optional[List[str]] = None) -> List[Dict]:
        """Retrieve all services registered with MOTHR

        Args:
            fields (list<str>, optional): Fields to return in the query response,
                default is `name` and `version`

        Returns:
            list<dict>: All services registered with MOTHR
        """
        fields = fields if fields is not None else ["name", "version"]
        fields = [self.resolve_field(self.ds.Service, field) for field in fields]
        q = self.ds.Query.services.select(*fields)
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = await ds.query(q)
        return resp["services"]

    def resolve_field(self, obj: DSLType, field: str) -> DSLField:
        """Resolve paths to nested fields

        Args:
            obj (`gql.dsl.DSLType`): Root type belonging to the field
            field (str): Field to resolve, nested fields are specified using
                dot notation

        Returns: `gql.dsl.DSLField`
        """
        if "." in field:
            nested_fields = self.field_map[str(obj._type)]
            f_split = field.split(".")
            return self.select_field(
                nested_fields, getattr(obj, f_split[0]), f_split[1:]
            )
        return getattr(obj, field)

    def select_field(
        self, field_map: Dict, field_obj: DSLField, field: List[str]
    ) -> DSLField:
        """Select nested fields

        Args:
            field_map (dict<str, `gql.dsl.DSLType`>): Dictionary mapping field names
                to their associated DSLType. See `self.field_map`
            field_obj (`gql.dsl.DSLField`): Field object to select subfields from
            field (list<str>): Field name split into individual components

        Returns: `gql.dsl.DSLField`
        """
        field_key = str(field_obj)
        for char in ["{", "}", "\n"]:
            field_key = field_key.replace(char, "")
        field_key = field_key.split(" ")[-1]
        field_name = field.pop(0)
        if len(field) > 0:
            return field_obj.select(
                self.select_field(
                    field_map, getattr(field_map[field_key], field_name), field
                )
            )
        return field_obj.select(getattr(field_map[field_key], field_name))
