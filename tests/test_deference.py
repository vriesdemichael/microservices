from pathlib import Path

import pytest
import requests
from dataformats.jsonschema.custom_types import SchemaType
from dataformats.jsonschema.mixins.dereference_mixin import (
    dereference,
    replace_schema_in_place,
    retrieve_schema,
)


def test_replace_ref_with_target():
    ref_object: SchemaType = {"$ref": "#some-ref"}
    original_id = id(ref_object)
    target: SchemaType = {"target_key": "target_value"}
    replace_schema_in_place(ref_object, target)
    assert original_id == id(ref_object)
    assert id(ref_object) != id(target)
    assert ref_object == target


# def test_ref_objects_with_scope_no_refs():
#     json_object = {"some_object": {"id": "has_id"}}
#     result = list(ref_objects_with_scope(json_object))
#     assert not result


# def test_ref_objects_with_scope_simple():
#     json_object = {"reffed_key": {"$ref": "ref"}}
#     refs_with_scope = list(ref_objects_with_scope(json_object))

#     assert len(refs_with_scope) == 1
#     ref, scopes = refs_with_scope[0]
#     assert ref == json_object["reffed_key"]
#     assert scopes == [json_object]


# def test_ref_objects_with_scope_simple_multiple():
#     json_object = {"reffed_key": {"id": "unimportant", "$ref": "ref"}}
#     refs_with_scope = list(ref_objects_with_scope(json_object))

#     assert len(refs_with_scope) == 1
#     ref, scopes = refs_with_scope[0]
#     assert ref == json_object["reffed_key"]
#     assert scopes == [json_object, json_object["reffed_key"]]


# def test_ref_objects_with_scope_complex():
#     json_object: dict[str, dict[str, Any]] = {
#         "a": {"id": "a_object", "$ref": "#/not/found/in/limited/scope"},
#         "b": {"$ref": "a_object"},
#         "c": {"id": "limited-scope", "c_ref": {"$ref": "#/c_target"}, "c_target": {"bingo": "bingo"}},
#     }

#     refs_with_scope = list(ref_objects_with_scope(json_object))
#     a_ref = refs_with_scope[0]
#     b_ref = refs_with_scope[1]
#     c_ref = refs_with_scope[2]

#     assert a_ref[0] == json_object["a"]
#     assert a_ref[1] == [json_object, json_object["a"]]

#     assert b_ref[0] == json_object["b"]
#     assert b_ref[1] == [json_object]

#     assert c_ref[0] == json_object["c"]["c_ref"]
#     assert c_ref[1] == [json_object, json_object["c"]]


def test_simple_inline_deref():
    json_object: SchemaType = {"definitions": {"target_key": "target_value"}, "b": {"$ref": "#/definitions"}}
    dereference(schema=json_object, download=False)
    assert json_object["b"] == json_object["definitions"]


# def test_find_ids():
#     json_object: SchemaType = {"definitions": {"a": {"id": "inline_id", "target_key": "target_value"}}, "items": {"$ref": "inline_id"}}
#     id_objects = objects_with_id(json_object, id_key="id")
#     assert "inline_id" in id_objects
#     assert id_objects["inline_id"] == json_object["definitions"]["a"]  # type: ignore


def test_id_based_inline_deref():
    json_object: SchemaType = {"definitions": {"a":{"id": "inline_id", "target_key": "target_value"}}, "items": {"$ref": "inline_id"}}
    dereference(schema=json_object, download=False)
    assert json_object["items"] == json_object["definitions"]["a"]  # type: ignore

def test_complex_id_based_inline_deref():
    schema = {
            "definitions": {
                "id_in_enum": {
                    "enum": [
                        {
                          "id": "https://localhost:1234/my_identifier.json",
                          "type": "null"
                        }
                    ]
                },
                "real_id_in_schema": {
                    "id": "https://localhost:1234/my_identifier.json",
                    "type": "string"
                },
                "zzz_id_in_const": {
                    "const": {
                        "id": "https://localhost:1234/my_identifier.json",
                        "type": "null"
                    }
                }
            },
            "anyOf": [
                { "$ref": "#/definitions/id_in_enum" },
                { "$ref": "https://localhost:1234/my_identifier.json" }
            ]
        }
    dereference(schema=schema, download=False)
    assert schema["anyOf"][0] == schema["definitions"]["id_in_enum"]  # type: ignore
    assert schema["anyOf"][1] == schema["definitions"]["real_id_in_schema"]  # type: ignore

    # TODO


# def test_id_schemas():
#     metaschema: JsonType = {"anyOf":[
#         {"id": "something"},
#         {"enum": {"id": "should not be found"}},
#     ]}
#     assert len(objects_with_id(metaschema, "id")) == 1

def test_empty_fragment_deref_one_level():
    json_object: SchemaType = {"a": {"$ref": "#"}}
    dereference(schema=json_object, download=False)
    assert "a" in json_object
    assert isinstance(json_object["a"], dict)
    assert "a" in json_object["a"]


# def test_objects_with_id_lists():
#     assert len(objects_with_id({"anyOf": [{"id": "target"}]}, id_key="id")) == 1


def test_retrieve_schema_file(remotes_dir: Path):
    integer_schema_path = remotes_dir / "integer.json"
    schema = retrieve_schema(integer_schema_path.absolute().as_uri(), download=False)
    assert schema == {"type": "integer"}


def test_retrieve_schema_remote():
    url = "http://localhost:1234/integer.json"
    schema = retrieve_schema(url, download=True)
    assert schema == {"type": "integer"}


def test_unsupported_schema():
    url = "ftp://localhost:1234/integer.json"
    with pytest.raises(ValueError, match="unsupported"):
        _ = retrieve_schema(url, download=True)


def test_retrieve_schema_remote_fail():
    url = "http://localhost:1234/nonexisting.json"
    with pytest.raises(requests.exceptions.HTTPError, match="404"):
        retrieve_schema(url, download=True)


# def test_find_base_uri_simple():
#     json_object: SchemaType = {"id": "http://absolute.com/schema.json"}
#     base_uri, base_schema = determine_baseuri_from_scopes(scopes=[json_object], id_key="id")
#     assert base_uri == json_object["id"]


# def test_find_base_uri_simple_change():
#     parent_schema: SchemaType = {"id": "http://absolute.com/schema.json", "child": {"id": "other-schema.json"}}
#     child_schema: SchemaType = typing.cast(SchemaType, parent_schema["child"])
#     base_uri, _ = determine_baseuri_from_scopes(scopes=[parent_schema, child_schema], id_key="id")
#     assert base_uri == "http://absolute.com/other-schema.json"


# def test_find_base_uri_simple_change_file(remotes_dir: Path):
#     integer_schema = remotes_dir / "integer.json"
#     parent_schema: SchemaType = {"id": integer_schema.as_uri(), "child": {"id": "name.json"}}
#     child_schema: SchemaType = typing.cast(SchemaType, parent_schema["child"])
#     base_uri, _ = determine_baseuri_from_scopes(scopes=[parent_schema, child_schema], id_key="id")
#     assert base_uri == (integer_schema.parent / "name.json").as_uri()


# def test_find_base_uri_no_absolute():
#     json_object: SchemaType = {"id": "i should be illegal"}
#     base_uri, _ = determine_baseuri_from_scopes(scopes=[json_object], id_key="id")
#     assert base_uri is None
