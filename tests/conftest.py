import functools
import time
from http.client import HTTPConnection
from pathlib import Path
from subprocess import PIPE, Popen
from typing import Any

import pydantic
import pytest
import requests
from dataformats.jsonschema.draft_4 import DRAFT4_SCHEMA

# from dataformats.jsonschema.pydantic_model import Draft4MetaSchema


# @pytest.fixture
# def draft_4_empty() -> Draft4MetaSchema:
#     return Draft4MetaSchema()


# @pytest.fixture()
# def draf_4_meta_self() -> Draft4MetaSchema:
#     return Draft4MetaSchema.model_validate(DRAFT4_SCHEMA)


@pytest.fixture(scope="session")
def remotes_dir():
    return Path(__file__).parent / "json_schema_test_suite" / "remotes"


# @pytest.fixture(scope="module")
# def static_server():
#     process = Popen(
#         ["python", "-m", "http.server", "8123", "--directory", root], stdout=PIPE
#     )
#     retries = 5
#     while retries > 0:
#         conn = HTTPConnection("localhost:8123")
#         try:
#             conn.request("HEAD", "/")
#             response = conn.getresponse()
#             if response is not None:
#                 yield process
#                 break
#         except ConnectionRefusedError:
#             time.sleep(1)
#             retries -= 1

#     if not retries:
#         raise RuntimeError("Failed to start http server")
#     else:
#         process.terminate()
#         process.wait()

@pytest.fixture(scope="session", autouse=True)
def http_server_process(remotes_dir: Path):
    """
    Call python's http.server module as a child process, wait for initialization and yield server for tests.
    """

    process = Popen(
        ["python", "-m", "http.server", "1234", "--directory", str(remotes_dir)], stdout=PIPE
    )

    retries = 5
    while retries > 0:
        conn = HTTPConnection('localhost:1234')
        try:
            conn.request('GET', '/integer.json')
            response = conn.getresponse()
            # conn.request("GET", "integer.json")
            # response = conn.getresponse()
            if response is not None:
                yield process
                break

        except ConnectionRefusedError:
            time.sleep(0.2)
            retries -= 1

    if not retries:
        raise RuntimeError("Failed to start http server")
    else:
        process.terminate()
        process.wait()

@pytest.fixture(autouse=True)
def patch_requests_to_localhost_remotes_server(monkeypatch: pytest.MonkeyPatch):
    with monkeypatch.context() as m:
        timeout_get = functools.partial(requests.get, timeout=0.01)
        m.setattr("requests.get", timeout_get)


class SchemaTestSuiteFile(pydantic.BaseModel):
    class SchemaTestObject(pydantic.BaseModel):
        class SchemaTest(pydantic.BaseModel):
            description: str
            data: Any
            valid: bool

        description: str
        test_schema: Any
        tests: list[SchemaTest]

    path: Path
    test_objects: list[SchemaTestObject]
