# aiomothr

![GitHub](https://img.shields.io/github/license/rs21io/aiomothr)

## Installation
`pip install aiomothr`

If you need to create a listener you need to install the optional listener
dependencies

`pip install aiomothr[listener]`

## Usage

```python
from aiomothr import AsyncJobRequest

request = AsyncJobRequest(service='echo')
request.add_parameter(value='Hello MOTHR!')
result = await request.run_job()
print(result)
```
