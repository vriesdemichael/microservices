import json
from pathlib import Path
from typing import Any, Generator, Iterable
from urllib.parse import ParseResult, urljoin, urlparse, urlunsplit

import requests
from dataformats.jsonschema.json_pointer import Pointer
from rfc3986 import URIReference

SchemaType = dict[str, Any]





def normalize_ref(ref: str) -> str:
    return URIReference.from_string(ref).normalize().unsplit()

def replace_ref_object_with_target_draft4(ref_object: SchemaType, target_object: SchemaType):
    """Draft 4 specific replace ref"""
    for key in ref_object:
        ref_object.pop(key)
    ref_object.update(target_object)
    return ref_object

def retrieve_absolute_uri(uri_parts: ParseResult, download: bool):
    if uri_parts.scheme == "file://":
        return json.loads(Path(uri_parts.path).read_text())
    elif uri_parts.scheme.startswith("http"):
        if download:
            response = requests.get(urlunsplit(uri_parts))
            response.raise_for_status()
            return response.json()
    else:
        raise ValueError(f"Encountered a ref with a unsupported scheme ({uri_parts.scheme})")

def find_base_uri(scope_list: list[Any], id_key) -> str:
    for scope in scope_list[::-1]:
        id: str = scope[id_key]
        parts = urlparse(id)
        if parts.scheme:
            # TODO get parent of current id
            return id
    raise ValueError("Could not find an absolute base uri")

def dereference(json_object, download=True, id_key="id", ref_key="$ref"):
    for ref_object, scope_list in ref_objects_with_scope(json_object):
        raw_ref = ref_object[ref_key]
        # Check for inline references by id first
        id_objects_top_level_scope = objects_with_id(scope_list[0])
        for id_object in id_objects_top_level_scope:
            if id_object[id_key] == raw_ref:
                # TODO double check if fragment should still be followed
                replace_ref_object_with_target_draft4(ref_object, id_object)
                return ref_object

        # then canonical
        uri_parts: ParseResult = urlparse(normalize_ref(raw_ref))

        if uri_parts.scheme or uri_parts.hostname:
            # TODO check if hostname and not scheme is valid
            target = retrieve_absolute_uri(uri_parts, download)

        elif uri_parts.hostname or uri_parts.path:
            base_uri = find_base_uri(scope_list, id_key)

            absolute_uri = urljoin(base_uri, uri_parts.path)
            target = retrieve_absolute_uri(urlparse(absolute_uri), download)
        else:
            # TODO double check
            target = scope_list[-1]

        if uri_parts.fragment:
            pointer = Pointer.from_string(uri_parts.fragment)
            target = pointer.follow_pointer(target)

        if not isinstance(target, dict):
            # TODO specialized exception in which the json_object, scope, ref are stored
            raise ValueError(f"Trying to dereference into a non schema target {urlunsplit(uri_parts)}")
        for key in ref_object:
            # draft 4 -> ignore all sibling keywords :(
            ref_object.pop(key)
        ref_object.update(target)


def ref_objects_with_scope(
    json_object: Any, scope: list[Any] | None=None,
    exclude : Iterable[str]=("default", "enum"),
    ref_key: str = "$ref",
    id_key: str = "id",
) -> Generator[tuple[SchemaType, list[SchemaType]], None, None]:
    """Find ref objects with their scopes

    Args:
        json_object: The object to  find refs in
        scope: The known scope for the object,
               the first in the list is the parent scope, the last is
               the most direct parent with a base uri. Defaults to None.

    Yields:
        A tuple of object with ref key, list of parent scopes
    """
    if scope is None:
        scope = []
        scope.append(json_object)

    if isinstance(json_object, dict):
        if id_key in json_object:
            scope.append(json_object)

        for key, value in json_object.items():
            if key not in exclude:
                yield from ref_objects_with_scope(value)
            if key == ref_key:
                yield json_object, scope
    elif isinstance(json_object, list):
        for item in json_object:
            yield from ref_objects_with_scope(item)


def objects_with_id(json_object: Any, exclude: Iterable[str]=("default", "enum"), id_key="id") -> Generator[Any, None, None]:
    """Find and return all objects with an id key in it
    This method is meant to be used on a specific scope
    """
    if isinstance(json_object, dict):
        for key, value in json_object.items():
            if key not in exclude:
                yield from objects_with_id(value)
            if key == id_key:
                yield json_object
    elif isinstance(json_object, list):
        for item in json_object:
            yield from objects_with_id(item)
    else:
        pass
