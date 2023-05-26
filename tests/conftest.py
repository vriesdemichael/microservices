from pathlib import Path
from typing import Any, Generator

import pydantic
import pytest
from dataformats.jsonschema.draft_4 import DRAFT4_SCHEMA
from dataformats.jsonschema.model import Draft4MetaSchema
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from httpx import Timeout


@pytest.fixture
def draft_4_empty() -> Draft4MetaSchema:
    return Draft4MetaSchema()


@pytest.fixture()
def draf_4_meta_self() -> Draft4MetaSchema:
    return Draft4MetaSchema.parse_obj(DRAFT4_SCHEMA)


@pytest.fixture()
def remotes_dir():
    return Path(__file__).parent / "json_schema_test_suite" / "remotes"


@pytest.fixture()
def patch_requests_to_localhost_remotes_server(
    remotes_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    app = FastAPI()
    app.mount("/", StaticFiles(directory=remotes_dir))
    client = TestClient(app, base_url="http://localhost:1234")
    with monkeypatch.context() as m:
        client.timeout = Timeout(0.1)
        m.setattr("requests.get", client.get)
        yield client


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
