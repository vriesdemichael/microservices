import pytest
from dataformats.jsonschema.custom_types import SchemaType
from dataformats.jsonschema.json_pointer import Pointer
from dataformats.jsonschema.mixins.schema_parsing import (
    absolute_id_map,
    find_parent_pointers,
    find_schemas,
    flatten_json,
    is_absolute,
    normalize,
    ref_map,
)


def test_flatten_json():
    json_schema: SchemaType = {"properties": {"somekey": {"allOf": [{"default": "somevalue"}]}}}
    flat_json_schema = flatten_json(json_schema)
    assert flat_json_schema[Pointer.from_string("/properties")] == json_schema["properties"]
    assert flat_json_schema[Pointer.from_string("/properties/somekey")] == json_schema["properties"]["somekey"]  # type: ignore
    assert flat_json_schema[Pointer.from_string("/properties/somekey/allOf")] == json_schema["properties"]["somekey"]["allOf"]  # type: ignore
    assert flat_json_schema[Pointer.from_string("/properties/somekey/allOf/0")] == json_schema["properties"]["somekey"]["allOf"][0]  # type: ignore
    assert flat_json_schema[Pointer.from_string("/properties/somekey/allOf/0/default")] == json_schema["properties"]["somekey"]["allOf"][0]["default"]  # type: ignore


def test_find_schemas():
    top_level_schema = {"definitions": {"a": {"id": "subschema"}}, "not-a-schema": {"type": "str"}}
    schemas = find_schemas(top_level_schema)
    # assert Pointer() in schemas
    assert Pointer.from_string("/definitions/a") in schemas
    assert Pointer.from_string("/note-a-schema") not in schemas


def test_find_schemas_():
    schema: SchemaType = {
        "definitions": {
            "actual ref": {"$ref": "#"},
        }
    }
    schemas = find_schemas(schema)
    assert len(schemas) == 2


def test_find_parent_pointer():
    child = Pointer.from_string("/some/nested/pointer")
    possible_parents = [
        Pointer.from_string("/some/nested"),
        Pointer.from_string("/some"),
        Pointer.from_string(""),
        Pointer.from_string("i dont belong here"),
    ]
    parent_iterator = find_parent_pointers(child, possible_parents)
    assert next(parent_iterator) == possible_parents[0]
    assert next(parent_iterator) == possible_parents[1]
    assert next(parent_iterator) == possible_parents[2]
    with pytest.raises(StopIteration):
        next(parent_iterator)


def test_normalize_defrag():
    uri = "HTTPs://www.ugLy.com/with space/index.html#fragment"
    normalized_uri = normalize(uri, defrag=True)
    assert normalized_uri == "https://www.ugly.com/with%20space/index.html"


def test_normalize_no_defrag():
    uri = "HTTPs://www.ugLy.com/with space/index.html#fragment"
    normalized_uri = normalize(uri, defrag=False)
    assert normalized_uri == "https://www.ugly.com/with%20space/index.html#fragment"


def test_is_absolute():
    assert is_absolute("file://somepath")
    assert is_absolute("https://www.jsonschema.org/")
    assert not is_absolute("other_schema.json")
    assert not is_absolute("../sibling.json#/defintions/a")


def test_absolute_id_map():
    schema = {
        "id": "https://schemstore.com/schemas/example.json",
        "definitions": {
            "relative_change": {"id": "other.json"},
            "relative_change_with_fragment": {"id": "another.json#withfragment"},
            "nested": {
                "id": "https://nested.com/parent.json",
                "items": {"$comment": "resolves to https://nested.com/child.json", "id": "child.json"},
            },
        },
    }
    absolute_ids = absolute_id_map(schema)
    # raise ValueError(absolute_ids.keys())
    assert absolute_ids[Pointer.from_string("")] == "https://schemstore.com/schemas/example.json"
    assert (
        absolute_ids[Pointer.from_string("/definitions/relative_change")] == "https://schemstore.com/schemas/other.json"
    )
    assert (
        absolute_ids[Pointer.from_string("/definitions/relative_change_with_fragment")]
        == "https://schemstore.com/schemas/another.json"
    )
    assert absolute_ids[Pointer.from_string("/definitions/nested/items")] == "https://nested.com/child.json"


def test_ref_map():
    schema: SchemaType = {
        "definitions": {
            "not a ref": {"$ref": 0},
            "also not ref": {"enum": [{"$ref": "#"}]},
            "actual ref": {"$ref": "#"},
            "ref deleted twice": {"enum": {"default": "$ref"}},
        }
    }
    refs = ref_map(schema)
    assert len(refs) == 1
    assert Pointer.from_string("/definitions/actual ref") in refs


@pytest.mark.xfail(
    raises=ValueError,
    reason="This should never occur, the id should always be set or fail when trying to do a relative deref without known id",
)
def test_id_map_no_id_top_level():
    schema: SchemaType = {
        "properties": {
            "derefenced_relative_id": {
                "id": "some_relative_id/i-was-imported.json",
                "properties": {
                    "relative_base_uri_change": {
                        "$comment": "This should resolve to some_relative_id/other.json",
                        "id": "other.json",
                    }
                },
            }
        }
    }
    absolute_ids = absolute_id_map(schema)
    assert len(absolute_ids) == 0
