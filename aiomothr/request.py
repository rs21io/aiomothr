# Copyright 2020 Resilient Solutions Inc. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from __future__ import annotations
import asyncio
import re
from typing import Dict, List, Optional
from warnings import warn

from gql import gql, Client
from gql.dsl import DSLSchema
from .client import AsyncMothrClient


class AsyncJobRequest:
    """Class used for managing asynchronous job requests sent to MOTHR

    Attributes:
        job_id (str): Request job id returned from self.submit()
        status (str): Status of the job

    Args:
        client (AsyncMothrClient): Client connection to use for requests
        service (str): Service being invoked by the request
        parameters (list<dict>, optional): Parameters to pass to the service
        broadcast (str, optional): PubSub channel to broadcast the job result to
        inputs (list<str>, optional): A list of S3 URIs to to be used as
            inputs by the service
        outputs (list<str>, optional): A list of S3 URIs to to be i
            uploaded by the service
        input_stream (str, optional): Value to pass to service through stdin
        output_metadata (dict): Metadata attached to job outputs
        version (str, optional): Version of the service, default `latest`
    """

    def __init__(self, **kwargs):
        self.client = kwargs.pop("client", AsyncMothrClient())
        kwargs["parameters"] = kwargs.get("parameters", [])
        kwargs["outputMetadata"] = kwargs.get("output_metadata", {})
        self.req_args = kwargs
        self.job_id = None
        self.status = None

    @staticmethod
    def is_s3_uri(uri: str) -> bool:
        """Checks if string matches the pattern s3://<bucket>/<key>"""
        return bool(re.match(r"^s3\:\/\/[a-zA-Z0-9\-\.]+[a-zA-Z]\/\S*?$", uri))

    def add_parameter(
        self, value: str, param_type: str = "parameter", name: Optional[str] = None
    ) -> AsyncJobRequest:
        """Add an parameter to the job request

        Args:
            value (str): Parameter value
            param_type (str, optional): Parameter type, one of
                (`parameter`, `input`, `output`). Default `parameter`
            name (str, optional): Parameter name/flag (e.g., `-i`, `--input`)
        """
        if self.job_id is not None:
            warn(
                "job has already been submitted, "
                "adding additional parameters will have no effect"
            )
        if param_type in ["input", "output"] and not self.is_s3_uri(value):
            warn(f"{param_type} parameter {value} is not an S3 URI")
        parameter = {"type": param_type, "value": value}
        if name is not None:
            parameter["name"] = name
        self.req_args["parameters"].append(parameter)
        return self

    def add_input(self, value: str, name: Optional[str] = None) -> AsyncJobRequest:
        """Add an input parameter to the job request"""
        return self.add_parameter(value, param_type="input", name=name)

    def add_output(self, value: str, name: Optional[str] = None) -> AsyncJobRequest:
        """Add an output parameter to the job request"""
        return self.add_parameter(value, param_type="output", name=name)

    def add_output_metadata(self, metadata: Dict[str, str]) -> AsyncJobRequest:
        """Add metadata to job outputs

        Args:
            metadata (dict)
        """
        if self.job_id is not None:
            warn(
                "job has already been submitted, "
                "adding additional output metadata will have no effect"
            )
        self.req_args["outputMetadata"].update(metadata)
        return self

    async def submit(self) -> str:
        """Submit a job request to the service endpoint

        Returns:
            str: The unique job identifier
        """
        q = self.client.ds.Mutation.submit_job.args(request=self.req_args).select(
            self.client.ds.JobRequestResponse.job.select(
                self.client.ds.Job.job_id, self.client.ds.Job.status
            )
        )
        async with Client(
            transport=self.client.transport, schema=self.client.schema
        ) as sess:
            ds = DSLSchema(sess)
            resp = await ds.mutate(q)
        if "errors" in resp:
            raise ValueError("Error submitting job request: " + resp["errors"])
        self.job_id = resp["submitJob"]["job"]["jobId"]
        self.status = resp["submitJob"]["job"]["status"]
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
            raise ValueError("Job ID is None, have you submitted the job?")

        fields = [
            self.client.resolve_field(self.client.ds.Job, field) for field in fields
        ]
        q = self.client.ds.Query.job.args(jobId=self.job_id).select(*fields)
        async with Client(
            transport=self.client.transport, schema=self.client.schema
        ) as sess:
            ds = DSLSchema(sess)
            resp = await ds.query(q)
        return resp["job"]

    async def check_status(self) -> str:
        """Check the current status of the job request

        Returns:
            str: Job status
        """
        job = await self.query_job(fields=["status"])
        return job["status"]

    async def result(self) -> Dict[str, str]:
        """Get the job result

        Returns:
            dict: Complete response from the job query
        """
        return await self.query_job(
            fields=["jobId", "service", "status", "result", "error"]
        )

    async def subscribe(self) -> str:
        """Subscribe to job"""
        s = gql(
            f"""
            subscription {{
                subscribeJobComplete(jobId: "{self.job_id}") {{
                    jobId
                    service
                    status
                    result
                    error
                }}
            }}
        """
        )
        async with Client(
            transport=self.client.ws_transport, schema=self.client.schema
        ) as sess:
            result = [r async for r in sess.subscribe(s)]
        return result[0]

    async def subscribe_messages(self):
        """Subscribe to job messages"""
        s = gql(
            f"""
            subscription {{
                subscribeJobMessages(jobId: "{self.job_id}")
            }}
        """
        )
        async with Client(
            transport=self.client.ws_transport, schema=self.client.schema
        ) as sess:
            async for result in sess.subscribe(s):
                print(result)
                yield result

    async def run_job(
        self, poll_frequency: float = 0.25, return_failed: bool = False
    ) -> Dict[str, str]:
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
        while status in ["submitted", "running"]:
            status = await self.check_status()
            await asyncio.sleep(poll_frequency)

        result = await self.result()
        if status != "complete" and return_failed is False:
            raise RuntimeError("Job {} failed: {}".format(job_id, result["error"]))
        return result
