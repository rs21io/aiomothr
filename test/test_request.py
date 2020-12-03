import pytest
from aiomothr import AsyncJobRequest, AsyncMothrClient
from asynctest import CoroutineMock, MagicMock, patch


# For mocking async loops
class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration


class TestJob:
    def setup_method(self, _):
        self.submit_response = {
            "submitJob": {"job": {"jobId": "test", "status": "submitted"}}
        }
        self.query_response = [
            {"job": {"status": "submitted"}},
            {"job": {"status": "running"}},
            {"job": {"status": "complete"}},
            {"job": {"status": "complete"}},
        ]

    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.mutate", new_callable=CoroutineMock)
    @patch("gql.dsl.DSLSchema.query", new_callable=CoroutineMock)
    async def test_run_job(self, mock_query, mock_mutate):
        mock_mutate.return_value = self.submit_response
        mock_query.side_effect = self.query_response
        request = AsyncJobRequest(service="test")
        result = await request.run_job()
        assert result

    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.mutate", new_callable=CoroutineMock)
    @patch("gql.dsl.DSLSchema.query", new_callable=CoroutineMock)
    async def test_run_job_fail(self, mock_query, mock_mutate):
        for i in [-1, -2]:
            self.query_response[i]["job"]["status"] = "failed"
            self.query_response[i]["job"]["error"] = "failed"
        mock_mutate.return_value = self.submit_response
        mock_query.side_effect = self.query_response
        request = AsyncJobRequest(service="test")
        with pytest.raises(RuntimeError):
            result = await request.run_job()

    @pytest.mark.asyncio
    @patch("gql.dsl.DSLSchema.mutate", new_callable=CoroutineMock)
    @patch("gql.dsl.DSLSchema.query", new_callable=CoroutineMock)
    async def test_run_job_fail_return_failed(self, mock_query, mock_mutate):
        for i in [-1, -2]:
            self.query_response[i]["job"]["status"] = "failed"
            self.query_response[i]["job"]["error"] = "failed"
        mock_mutate.return_value = self.submit_response
        mock_query.side_effect = self.query_response
        request = AsyncJobRequest(service="test")
        result = await request.run_job(return_failed=True)
        assert result["error"] == "failed"

    @pytest.mark.asyncio
    @patch("aiomothr.request.Client")
    async def test_subscribe(self, mock_client):
        mock_client.return_value.__aenter__.return_value.subscribe.return_value = (
            AsyncIterator(["test"])
        )
        request = AsyncJobRequest(service="test")
        result = await request.subscribe()
        assert result == "test"

    @pytest.mark.asyncio
    @patch("aiomothr.request.Client")
    async def test_subscribe_messages(self, mock_client):
        mock_client.return_value.__aenter__.return_value.subscribe.return_value = (
            AsyncIterator([f"message {i+1}" for i in range(10)])
        )
        request = AsyncJobRequest(service="test")
        messages = [m async for m in request.subscribe_messages()]
        assert len(messages) == 10
        assert messages[0] == "message 1"

    def test_method_chaining(self):
        request = AsyncJobRequest(service="test")
        request.add_input(value="s3://bucket/test.txt").add_output(
            value="s3://bucket/test.txt"
        ).add_parameter(value="baz").add_output_metadata({"foo": "bar"})
        assert len(request.req_args["parameters"]) == 3
        assert request.req_args["parameters"][0]["type"] == "input"
        assert request.req_args["parameters"][1]["type"] == "output"
        assert request.req_args["parameters"][2]["type"] == "parameter"
        assert request.req_args["outputMetadata"]["foo"] == "bar"

    def test_add_parameter_warn(self):
        request = AsyncJobRequest(service="test")
        request.job_id = "test"
        with pytest.warns(UserWarning):
            request.add_parameter(value="foo")

    def test_add_input_warn(self):
        request = AsyncJobRequest(service="test")
        with pytest.warns(UserWarning):
            request.add_input(value="foo")

    def test_add_output_metadata_warn(self):
        request = AsyncJobRequest(service="test")
        request.job_id = "test"
        with pytest.warns(UserWarning):
            request.add_output_metadata({"foo": "bar"})
