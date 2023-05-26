import pytest
import requests
from dataformats.jsonschema.model import Draft4MetaSchema
from dataformats.jsonschema.validations import validate


def test_tesclient(patch_requests_to_localhost_remotes_server):
    requests.get("http://localhost/integer.json")

def test_model_fields():
    pass

# def test_subschema():
#     schema = Draft4MetaSchema.parse_obj({"integer": {"type": "integer"}, "refToInteger": {"$ref": "#/integer"}})
#     print(schema)

# @pytest.mark.skip
def test_validate_WIP(patch_requests_to_localhost_remotes_server):
    schema = {'additionalProperties': False, 'properties': {'foo': {'$ref': '#'}}}
    data = {'foo': {'bar': False}}
    is_valid = False

    # Draft4MetaSchema.parse_obj({"definitions": {"foo": {"type": 1}}})
    parsed_schema = Draft4MetaSchema.parse_obj(schema)
    print(parsed_schema)
    errors = validate(data, parsed_schema)
    if errors and is_valid:
        print(f"{is_valid=}")
        print(errors)
        print(list(errors.values())[0][0].__notes__)
        first_level = list(errors.values())[0][0]
        second_level = list(first_level.errors.values())[0][0]  # type: ignore
        print(second_level)
        raise ValueError("Got errors")
    elif not errors and not is_valid:
        print(f"Schema with fault = {parsed_schema}")
        raise ValueError("False negative")
