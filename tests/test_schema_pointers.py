import pytest
from dataformats.jsonschema.mixins.json_pointer_schema_regex import (
    valid_schema_pointers,
)


@pytest.mark.parametrize('keyword', ["additionalItems","items", "additionalProperties", "not", ""])
def test_direct_location(keyword: str):
    assert valid_schema_pointers.match(f"/{keyword}")

@pytest.mark.parametrize('keyword', ["definitions", "properties", "patternProperties", "dependencies"])
def test_object_location(keyword: str):
    assert valid_schema_pointers.match(f"/{keyword}/somekey")  # TODO fuzz with hypothesis

@pytest.mark.parametrize('keyword', ["items", "allOf", "anyOf", "oneOf"])
def test_array_location(keyword: str):
    assert valid_schema_pointers.match(f"/{keyword}/123")  # TODO fuzz with hypothesis


def test_direct_parent_not_a_schema():
    assert not valid_schema_pointers.match("/something/not")

def test_nested_location():
    assert valid_schema_pointers.match("/definitions/somekey/anyOf/123/not")


def test_array_with_key():
    assert not valid_schema_pointers.match("/items/key")


def test_object_with_index():
    assert valid_schema_pointers.match("/definitions/1")


def test_top_level():
    assert valid_schema_pointers.match("")
