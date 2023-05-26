from pathlib import Path
from typing import Any

import httpx
import pytest
from dataformats.jsonschema.dereference import (
    dereference,
    find_base_uri,
    objects_with_id,
    ref_objects_with_scope,
    replace_ref_object_with_target_draft4,
    retrieve_absolute_uri,
)


def test_replace_ref_with_target():
    ref_object = {"$ref": "#some-ref"}
    original_id = id(ref_object)
    target = {"target_key": "target_value"}
    replace_ref_object_with_target_draft4(ref_object, target)
    assert original_id == id(ref_object)
    assert id(ref_object) != id(target)
    assert ref_object == target


def test_ref_objects_with_scope_no_refs():
    json_object = {"some_object": {"id": "has_id"}}
    result = list(ref_objects_with_scope(json_object))
    assert not result


def test_ref_objects_with_scope_simple():
    json_object = {"reffed_key": {"$ref": "ref"}}
    refs_with_scope = list(ref_objects_with_scope(json_object))

    assert len(refs_with_scope) == 1
    ref, scopes = refs_with_scope[0]
    assert ref == json_object["reffed_key"]
    assert scopes == [json_object]


def test_ref_objects_with_scope_simple_multiple():
    json_object = {"reffed_key": {"id": "unimportant", "$ref": "ref"}}
    refs_with_scope = list(ref_objects_with_scope(json_object))

    assert len(refs_with_scope) == 1
    ref, scopes = refs_with_scope[0]
    assert ref == json_object["reffed_key"]
    assert scopes == [json_object, json_object["reffed_key"]]


def test_ref_objects_with_scope_complex():
    json_object: dict[str, dict[str, Any]] = {
        "a": {"id": "a_object", "$ref": "#/not/found/in/limited/scope"},
        "b": {"$ref": "a_object"},
        "c": {"id": "limited-scope", "c_ref": {"$ref": "#/c_target"}, "c_target": {"bingo": "bingo"}},
    }

    refs_with_scope = list(ref_objects_with_scope(json_object))
    a_ref = refs_with_scope[0]
    b_ref = refs_with_scope[1]
    c_ref = refs_with_scope[2]

    assert a_ref[0] == json_object["a"]
    assert a_ref[1] == [json_object, json_object["a"]]

    assert b_ref[0] == json_object["b"]
    assert b_ref[1] == [json_object]

    assert c_ref[0] == json_object["c"]["c_ref"]
    assert c_ref[1] == [json_object, json_object["c"]]


def test_simple_inline_deref():
    json_object = {"a": {"target_key": "target_value"}, "b": {"$ref": "#/a"}}
    dereference(json_object)
    assert json_object["b"] == json_object["a"]


def test_find_ids():
    json_object = {"a": {"id": "inline_id", "target_key": "target_value"}, "b": {"$ref": "inline_id"}}
    id_objects = objects_with_id(json_object)
    assert next(id_objects) == json_object["a"]


def test_id_based_inline_deref():
    json_object = {"a": {"id": "inline_id", "target_key": "target_value"}, "b": {"$ref": "inline_id"}}
    dereference(json_object)
    assert json_object["b"] == json_object["a"]

def test_empty_fragment_deref():
    json_object = {"a": {"$ref": "#"}}
    dereference(json_object)
    assert "a" in json_object["a"]


def test_objects_with_id_lists():
    assert len(list(objects_with_id([{"id": "target"}]))) == 1


def test_find_refs_within_list():
    refs = list(ref_objects_with_scope({"some_refs_in_a_list": [{"$ref": "..."}, {"$ref": ",,,"}]}))
    assert len(refs) == 2


def test_retrieve_schema_file(remotes_dir: Path):
    integer_schema = remotes_dir / "integer.json"
    schema = retrieve_absolute_uri(integer_schema.absolute().as_uri(), download=False)
    assert schema == {"type": "integer"}


def test_retrieve_schema_remote(patch_requests_to_localhost_remotes_server):
    url = "http://localhost:1234/integer.json"
    schema = retrieve_absolute_uri(url, download=True)
    assert schema == {"type": "integer"}


def test_unsupported_schema():
    url = "ftp://localhost:1234/integer.json"
    with pytest.raises(ValueError, match="unsupported"):
        _ = retrieve_absolute_uri(url, download=True)


def test_retrieve_schema_remote_fail(patch_requests_to_localhost_remotes_server):
    url = "http://localhost:1234/nonexisting.json"
    with pytest.raises(httpx.HTTPStatusError, match="404"):
        retrieve_absolute_uri(url, download=True)


def test_find_base_uri_simple():
    json_object = {"id": "http://absolute.com/schema.json"}
    base_uri = find_base_uri(scope_list=[json_object], id_key="id")
    assert base_uri == json_object["id"]


def test_find_base_uri_simple_change():
    json_object = {"id": "http://absolute.com/schema.json", "child": {"id": "other-schema.json"}}
    base_uri = find_base_uri(scope_list=[json_object, json_object["child"]], id_key="id")
    assert base_uri == "http://absolute.com/other-schema.json"


def test_find_base_uri_simple_change_file(remotes_dir: Path):
    integer_schema = remotes_dir / "integer.json"
    json_object = {"id": integer_schema.as_uri(), "child": {"id": "name.json"}}
    base_uri = find_base_uri(scope_list=[json_object, json_object["child"]], id_key="id")
    assert base_uri == (integer_schema.parent / "name.json").as_uri()


def test_find_base_uri_no_absolute():
    json_object = {"id": "i should be illegal"}
    base_uri = find_base_uri(scope_list=[json_object], id_key="id")
    assert base_uri is None
