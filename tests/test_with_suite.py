import json
from pathlib import Path

import pytest
from dataformats.jsonschema.model import Draft4MetaSchema
from dataformats.jsonschema.validations import validate


def draft4_testsuite():
    draf4_tests_path = Path(__file__).parent / "json_schema_test_suite" / "tests" / "draft4"
    all_json = draf4_tests_path.glob("**/*.json")

    for test_file in all_json:
        relative_path = test_file.relative_to(draf4_tests_path)
        try:
            test_objects = json.loads(test_file.read_text(encoding="utf-8"))
        except Exception as e:
            assert e is True
            raise
            # raise
        for test_object in test_objects:
            test_object_description = test_object["description"]
            test_object_schema = test_object["schema"]
            test_object_tests = test_object["tests"]
            for test_object_test in test_object_tests:
                test_description = test_object_test["description"]
                test_data = test_object_test["data"]
                test_valid = test_object_test["valid"]

                id = f"{relative_path}  | {test_object_description} | {test_description} "
                # if "ecmascript" not in str(relative_path): # TODO later
                if "optional" not in str(relative_path) and "" in id:

                    yield pytest.param(test_object_schema, test_data, test_valid, id=id)


argvalues = list(draft4_testsuite())

@pytest.mark.skip
@pytest.mark.parametrize(argnames="schema, data, is_valid", argvalues=argvalues, )
def testsuite(schema, data, is_valid: bool, patch_requests_to_localhost_remotes_server: None):
    # try:
    parsed_schema = Draft4MetaSchema.parse_obj(schema)
    # except Exception as e:


    errors = validate(instance=data, schema=parsed_schema)
    has_errors = bool(errors)

    if is_valid:
        pass
        if has_errors:
            # raise ValueError(errors)
            print(errors)
            assert "false_negative" == True
        else:
            # raise ValueError("True positive")
            pass  # True positive
    else:
        if has_errors:
            # raise ValueError("True negative")
            pass # True negative
        else:
            # false postive, ignore until all validations are implemented
            assert "false_positive" == True

    # if is_valid and has_errors:
    #     raise ValueError(errors)
    # if not is_valid and not has_errors:
    #     # raise ValueError("False positive")
    #     pass


    #     raise ValueError(errors)
    # # assert not has_errors == is_valid


    # TODO build validation method :)
