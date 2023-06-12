import logging
from urllib.parse import ParseResult, urldefrag, urljoin, urlparse

from dataformats.jsonschema.custom_types import JsonType, SchemaType
from dataformats.jsonschema.json_pointer import Pointer
from dataformats.jsonschema.mixins.json_pointer_schema_regex import (
    valid_schema_pointers,
)
from rfc3986 import URIReference

logger = logging.getLogger()


def find_schemas(schema: SchemaType) -> dict[Pointer, SchemaType]:
    """Find schemas in the given json object, this function assumes that the given json object is a schema

    Args:
        json_object: A schema object

    Returns:
        A dict of json pointer to schema
    """
    flat_json_mapping = flatten_json(schema)
    # flat_json_keys = [str(k) for k in flat_json_mapping.keys()]
    # for x in flat_json_keys:
    #     logger.info(x)
    flat_schema_mapping = {k: v for k, v in flat_json_mapping.items() if valid_schema_pointers.match(str(k))}
    # logger.info(f"{flat_schema_mapping.keys()=}")
    flat_schema_mapping_valid_types: dict[Pointer, SchemaType] = {
        k: v for k, v in flat_schema_mapping.items() if isinstance(v, dict)
    }
    # flat_schema_map_types = {k: type(v) for k, v in flat_schema_mapping.items()}
    # logger.info(f"{flat_schema_map_types=}")

    return flat_schema_mapping_valid_types

def find_parent_pointers(current_pointer: Pointer, pointers: list[Pointer]):
    sorted_by_length = sorted(pointers, key=lambda x: -len(x))
    for pointer in sorted_by_length:
        if current_pointer.is_child_of(pointer):
            yield pointer

def normalize(uri: str, defrag=False):
    if defrag:
        uri, _ = urldefrag(uri)
    return URIReference.from_string(uri).normalize().unsplit()

def is_absolute(uri: str):
    normalized_uri = normalize(uri, defrag=True)
    uri_parts: ParseResult = urlparse(normalized_uri)

    is_absolute = uri_parts.scheme or uri_parts.hostname
    return is_absolute


def absolute_id_map(root_object: SchemaType, id_key="id") -> dict[Pointer, str]:
    """Find absolute ids for the given object

    Args:
        root_object: The object to make the ids absolute for
        id_key: Defaults to "id".

    returns
    A dict of pointer -> absolute id
    """
    schema_map = find_schemas(root_object)
    pointer_id_map: dict[Pointer, str] = {pointer: schema_id for pointer, schema in schema_map.items() if id_key in schema and isinstance(schema_id := schema[id_key], str)}
    pointer_absolute_id_map: dict[Pointer, str] = {}
    pointers_sorted_by_size = sorted(pointer_id_map.keys(), key=lambda x: len(x))
    for pointer in pointers_sorted_by_size:
        parents = list(find_parent_pointers(pointer, list(pointer_id_map.keys())))

        new_id = pointer_id_map[pointer]
        while not is_absolute(new_id):
            if not parents:  # TODO should this raise?
                raise ValueError(f"Could not find a base uri for {pointer}, no more parents left to determine the base uri. Currently at {new_id} as relative uri")
            parent_pointer = parents.pop(0)
            parent_id = pointer_id_map[parent_pointer]

            new_id = urljoin(f"{normalize(parent_id, defrag=True)}/", f"../{normalize(new_id, defrag=True)}")

        pointer_absolute_id_map[pointer] = new_id
    return pointer_absolute_id_map

def ref_map(root_object: SchemaType, ref_key="$ref", exclude=("enum", "default")):
    schema_map = find_schemas(root_object)
    ref_pointers = {pointer: schema[ref_key] for pointer, schema in schema_map.items() if ref_key in schema and isinstance(schema[ref_key], str)}
    logger.info(ref_pointers)
    # filter naughty refs within excluded keywords
    for pointer in list(ref_pointers.keys()):
        for excluded_key in exclude:
            if excluded_key in pointer.parts and pointer in ref_pointers:
                ref_pointers.pop(pointer)
    return ref_pointers

def flatten_json(json_object: JsonType):
    """Flattens json stucture to a map of json pointer strings to their objects"""
    return _flatten_object_to_pointers(json_object)


def _flatten_object_to_pointers(
    json_object: JsonType,
    _pointer_mapping: dict[Pointer, JsonType] | None = None,
    _pointer: Pointer | None = None,
):
    if not _pointer_mapping:
        _pointer_mapping = {}
    if not _pointer:
        _pointer = Pointer.from_string("")


    if id(json_object) in [id(x) for x in _pointer_mapping.values()]:  # recursion
        logger.info(f"Recursion {json_object=} {_pointer_mapping.values()}")
        return _pointer_mapping


    _pointer_mapping[_pointer] = json_object


    if isinstance(json_object, dict):
        for key, value in json_object.items():
            if key == "actual ref":
                logger.info("Found key ")
            _flatten_object_to_pointers(value, _pointer_mapping, _pointer.extended_copy(key))
            if key == "actual ref":
                logger.info(f"{_pointer_mapping.keys()=}")
    elif isinstance(json_object, list):
        for idx, value in enumerate(json_object):
            _flatten_object_to_pointers(value, _pointer_mapping, _pointer.extended_copy(str(idx)))
    return _pointer_mapping
