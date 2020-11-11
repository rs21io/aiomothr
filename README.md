# aiomothr

![GitHub](https://img.shields.io/github/license/rs21io/aiomothr)
![Actions](https://github.com/rs21io/aiomothr/workflows/tests/badge.svg)
[![codecov](https://codecov.io/gh/rs21io/aiomothr/branch/main/graph/badge.svg)](https://codecov.io/gh/rs21io/aiomothr)

## Installation
`pip install aiomothr`

## Usage

Basic example submitting a job request

```python
from aiomothr import AsyncJobRequest

request = AsyncJobRequest(service="echo")
request.add_parameter(value="Hello MOTHR!")
result = await request.run_job()
print(result)
```

Submitting a job request Using `AsyncMothrClient`. This allows you to reuse the
client connection when making multiple requests.

```python
from mothrpy import AsyncJobRequest, AsyncMothrClient

client = AsyncMothrClient()

# Send one request
request = AsyncJobRequest(client=client, service="echo")
request.add_parameter(value="Hello MOTHR!")
result = await request.run_job()
print(result)

# Reuse the client in another request
request = AsyncJobRequest(client=client, service="echo")
request.add_parameter(value="Hello again MOTHR!")
result = await request.run_job()
print(result)
```

Submit concurrent job requests

```python
import asyncio

from mothrpy import AsyncJobRequest, AsyncMothrClient

client = AsyncMothrClient()

request_a = AsyncJobRequest(client=client, service="echo")
request_a.add_parameter(value="Hello MOTHR!")

request_b = AsyncJobRequest(client=client, service="echo")
request_b.add_parameter(value="Hello again MOTHR!")

# Execute both requests concurrently
tasks = [request_a.run_job(), request_b.run_job()]
results = await asyncio.gather(*tasks)

for result in results:
  print(result)
```
