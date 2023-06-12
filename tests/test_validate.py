import pytest
import requests
from dataformats.jsonschema.mixins.validations_mixin import Draft4Validator


def test_testclient():
    requests.get("http://localhost:1234/integer.json")

@pytest.mark.parametrize("shut_up_ruff", "")
def test_model_fields(shut_up_ruff):
    pass

# def test_subschema():
#     schema = Draft4MetaSchema.parse_obj({"integer": {"type": "integer"}, "refToInteger": {"$ref": "#/integer"}})
#     print(schema)

# @pytest.mark.skip
def test_validate_WIP(patch_requests_to_localhost_remotes_server):

    # validator.derefence()

    schema = {'items': [{'type': 'integer'}, {'type': 'integer'}]}
    data = [1, 2]
    is_valid = True



    validator = Draft4Validator(**schema)
    errors = validator.validate(data)



    if errors and is_valid:
        print(f"{is_valid=}")
        print(errors)
        print(list(errors.values())[0][0].__notes__)
        first_level = list(errors.values())[0][0]
        second_level = list(first_level.errors.values())[0][0]  # type: ignore
        print(second_level)
        raise ValueError("Got errors")
    elif not errors and not is_valid:
        print(f"Schema with fault = {validator}")
        raise ValueError(f"False negative {validator}")


def test_repr():
    repr(Draft4Validator("", ))
