# Copyright 2020 Resilient Solutions Inc. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import aiohttp
import asyncio
import os
from gql import gql, AIOHTTPTransport, Client, WebsocketsTransport
from gql.dsl import DSLSchema
from mothrpy import JobRequest
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit


with open(os.path.join(os.path.realpath(os.path.dirname(__file__)), 'schema.graphql')) as f:
    schema = f.read()


class AsyncJobRequest(JobRequest):
    """Object used for submitting asynchronous requests to mothr

    Attributes:
        job_id (str): Request job id returned from self.submit()
        status (str): Status of the job

    Args:
        service (str): Service being invoked by the request
        parameters (list<dict>, optional): Parameters to pass to the service
        broadcast (str, optional): PubSub channel to broadcast the job result to
        inputs (list<str>, optional): A list of S3 URIs to to be used as inputs by the service
        outputs (list<str>, optional): A list of S3 URIs to to be uploaded by the service
        input_stream (str, optional): Value to pass to service through stdin
        output_metadata (dict): Metadata attached to job outputs
        version (str, optional): Version of the service, default `latest`
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
    def __init__(self, *args, **kwargs):
        schemes = {'http': 'ws', 'https': 'wss'}
        self.headers: Dict[str, str] = {}
        endpoint = os.environ.get('MOTHR_ENDPOINT', 'http://localhost:8080/query')
        url = kwargs.pop('url', endpoint)
        split_url = urlsplit(url)
        ws_url = urlunsplit(split_url._replace(scheme=schemes[split_url.scheme]))

        self.transport = AIOHTTPTransport(url=url, headers=self.headers)
        self.ws_transport = WebsocketsTransport(url=ws_url)

        token = kwargs.pop('token', os.environ.get('MOTHR_ACCESS_TOKEN'))
        username = kwargs.pop('username', None)
        password = kwargs.pop('password', None)
        if username is None:
            username = os.environ.get('MOTHR_USERNAME')
        if password is None:
            password = os.environ.get('MOTHR_PASSWORD')
        if token is not None:
            self.headers = {'Authorization': f'Bearer {token}'}
        elif None not in (username, password):
            loop = asyncio.get_event_loop()
            token, refresh = loop.run_until_complete(self.login(username, password))
            self.headers = {'Authorization': f'Bearer {token}'}

        kwargs['parameters'] = kwargs.get('parameters', [])
        kwargs['outputMetadata'] = kwargs.get('output_metadata', {})
        self.req_args = kwargs
        self.job_id = None
        self.status = None

    async def login(self, username: Optional[str]=None, password: Optional[str]=None) -> Tuple[str, Optional[str]]:
        """Retrieve a web token from mothr

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
        token = os.environ.get('MOTHR_ACCESS_TOKEN')
        if token is not None:
            return token, None

        username = username if username is not None \
            else os.environ.get('MOTHR_USERNAME')
        password = password if password is not None \
            else os.environ.get('MOTHR_PASSWORD')
        if username is None:
            raise ValueError('Username not provided')
        if password is None:
            raise ValueError('Password not provided')

        credentials = {'username': username, 'password': password}
        client = Client(schema=schema)
        ds = DSLSchema(client)
        q = (ds.Mutation.login
             .args(**credentials)
             .select(ds.LoginResponse.token,
                     ds.LoginResponse.refresh))
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = ds.mutate(q)
        tokens = resp['login']
        if tokens is None:
            raise ValueError('Login failed')
        access = tokens['token']
        refresh = tokens['refresh']
        os.environ['MOTHR_ACCESS_TOKEN'] = access
        os.environ['MOTHR_REFRESH_TOKEN'] = refresh
        return access, refresh

    async def refresh_token(self) -> str:
        """Refresh an expired access token

        Returns:
            str: New access token
        """
        current_token = self.headers.get('Authorization', '').split(' ')[-1]
        system_token = os.getenv('MOTHR_ACCESS_TOKEN', '')
        if current_token != system_token:
            token = system_token
        else:
            refresh = os.getenv('MOTHR_REFRESH_TOKEN')
            client = Client(schema=schema)
            ds = DSLSchema(client)
            q = (ds.Mutation.refresh.args(token=refresh))
            async with Client(transport=self.transport, schema=schema) as sess:
                ds = DSLSchema(sess)
                resp = ds.mutate(q)
            if resp['refresh'] is None:
                raise ValueError('Token refresh failed')
            token = resp['refresh']['token']
            os.environ['MOTHR_ACCESS_TOKEN'] = token
        self.headers['Authorization'] = f'Bearer {token}'
        return token

    async def submit(self) -> str:
        """Submit a job request to the service endpoint

        Returns:
            str: The unique job identifier
        """
        client = Client(schema=schema)
        ds = DSLSchema(client)
        q = (ds.Mutation.submit_job
             .args(request=self.req_args)
             .select(ds.JobRequestResponse.job
                     .select(ds.Job.job_id,
                             ds.Job.status)))
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = ds.mutate(q)
        if 'errors' in resp:
            raise ValueError('Error submitting job request: ' + resp['errors'])
        self.job_id = resp['submitJob']['job']['jobId']
        self.status = resp['submitJob']['job']['status']
        return self.job_id

    async def query_job(self, fields: List[str]) -> Dict[str, str]:
        """Query information about the job request

        Args:
            fields (list<str>): Fields to return in the query response

        Returns:
            dict: Query result for the job request

        Raises:
            ValueError: If job ID does not exist
        """
        if self.job_id is None:
            raise ValueError('Job ID is None, have you submitted the job?')

        client = Client(schema=schema)
        ds = DSLSchema(client)
        fields = [getattr(ds.Job, field) for field in fields]
        q = ds.Query.job.args(jobId=self.job_id).select(*fields)
        async with Client(transport=self.transport, schema=schema) as sess:
            ds = DSLSchema(sess)
            resp = ds.query(q)
        return resp['job']

    async def check_status(self) -> str:
        """Check the current status of the job request

        Returns:
            str: Job status
        """
        job = await self.query_job(fields=['status'])
        return job['status']

    async def result(self) -> Dict[str, str]:
        """Get the job result

        Returns:
            dict: Complete response from the job query
        """
        return await self.query_job(fields=['jobId', 'service', 'status', 'result', 'error'])

    async def subscribe(self) -> str:
        s = gql(f'''
            subscription {{
                subscribeJobComplete(jobId: "{self.job_id}") {{
                    jobId
                    service
                    status
                    result
                    error
                }}
            }}
        ''')
        async with Client(transport=self.ws_transport, schema=schema) as sess:
            result = [r async for r in sess.subscribe(s)]
        return result[0]

    async def subscribe_messages(self):
        s = gql(f'''
            subscription {{
                subscribeJobMessages(jobId: "{self.job_id}")
            }}
        ''')
        async with Client(transport=self.ws_transport, schema=schema) as sess:
            async for result in sess.subscribe(s):
                print(result)
                yield result

    async def run_job(self, poll_frequency: float=0.25, return_failed: bool=False) -> Dict[str, str]:
        """Execute the job request

        Args:
            poll_frequency (float, optional): Frequency, in seconds, to poll for job
                status. Default, poll every 0.25 seconds.
            return_failed (bool, optional): Return failed job results instead of
                raising an exception. Default False

        Returns:
            dict: The job result

            Example::

                {
                    'jobId': 'job-id',
                    'service': 'my-service',
                    'status': 'complete',
                    'result': '',
                    'error': ''
                }

        Raises:
            RuntimeError: If job returns a status of failed, unless explicitly
                specified to return failed jobs by setting `return_failed`
                parameter to True
        """
        job_id = await self.submit()
        status = await self.check_status()
        while status in ['submitted', 'running']:
            status = await self.check_status()
            await asyncio.sleep(poll_frequency)

        result = await self.result()
        if status == 'complete' or return_failed is True:
            return result
        else:
            raise RuntimeError('Job {} failed: {}'.format(job_id, result['error']))
