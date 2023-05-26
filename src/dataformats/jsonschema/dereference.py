import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Generator, Iterable
from urllib.parse import ParseResult, urljoin, urlparse, urlunsplit
from urllib.request import url2pathname

import requests
from dataformats.jsonschema.json_pointer import Pointer
from rfc3986 import URIReference

SchemaType = dict[str, Any]
logger = logging.getLogger(__name__)


# @dataclass
# class ReferenceToSchema:
#     pointer: str
#     reference: dict[str, Any]

#     def __getitem__(self, __key: Any):
#         self.reference.get(__key)
#     def __repr__(self):
#         return f"ReferenceToSchema(pointer={self.pointer}, reference=<ommited due to recursion>)"
#     def __str__(self):
#         return repr(self)
# class DictWithPointers(dict):
#     def __getitem__(self, __key: Any) -> Any:
#         value = super().__getitem__(__key)
#         if isinstance(value, ReferenceToSchema):
#             return value.reference

def replace_ref_object_with_target_draft4(ref_object: SchemaType, target_object: SchemaType):
    """Draft 4 specific replace ref"""
    for key in list(ref_object.keys()):
        ref_object.pop(key)
    ref_object.update(target_object)
    return ref_object

def retrieve_absolute_uri(uri: str, download: bool):
    uri_parts = urlparse(uri)
    logger.debug(f"{uri_parts=}")
    if uri_parts.scheme == "file":
        return json.loads(Path(url2pathname(uri_parts.path)).read_text())
    elif uri_parts.scheme.startswith("http"):
        if download:
            response = requests.get(uri)
            response.raise_for_status()
            return response.json()
    else:
        raise ValueError(f"Encountered a ref with a unsupported scheme ({uri_parts.scheme})")

def find_base_uri(scope_list: list[Any], id_key) -> str | None:
    relative_path = ""
    for scope in scope_list[::-1]:
        if id_key in scope:
            id = scope[id_key]
            parts: ParseResult = urlparse(id)
            if parts.scheme:
                # redundant slashes for consistent behaviour of urljoin
                if relative_path:
                    absolute_id_of_most_direct_parent = urljoin(f"{id}/", f"../{relative_path}")
                else:
                    return id
                return absolute_id_of_most_direct_parent
            else:
                relative_path = urljoin(f"{relative_path}/", f"../{id}")

    return None

def dereference(json_object, download=True, id_key="id", ref_key="$ref"):
    for ref_object, scope_list in list(ref_objects_with_scope(json_object)):
        raw_ref = ref_object[ref_key]
        # Check for inline references by id first
        id_to_object_map = {x.get(id_key): x for x in objects_with_id(scope_list[0]) if id_key in x}
        if target := id_to_object_map.get(raw_ref, None):
            replace_ref_object_with_target_draft4(ref_object, target)
            logger.debug(f"Dereffed from inline id {raw_ref}")
            continue


        # then canonical
        normalized_uri = URIReference.from_string(raw_ref).normalize().unsplit()
        uri_parts: ParseResult = urlparse(normalized_uri)
        logger.debug(f"got {uri_parts=}")
        if uri_parts.scheme or uri_parts.hostname:
            logger.debug("In absolute path")
            # TODO check if hostname and not scheme is valid
            target = retrieve_absolute_uri(uri_parts.geturl(), download)

        elif uri_parts.hostname or uri_parts.path:
            logger.debug(f"In relative with {uri_parts.path}")

            if not (base_uri := find_base_uri(scope_list, id_key)):
                raise ValueError(f"No absolute uri could be determined to resolve {raw_ref}")
            # TODO might mess up with a parent too high
            absolute_uri = urljoin(f"{base_uri}/", "../{uri_parts.path}")
            target = retrieve_absolute_uri(absolute_uri, download)
        else:
            logger.debug("In inline path")
            # TODO double check
            # print(f"{scope_list=}")
            # raise ValueError(f"{scope_list=}")
            target = scope_list[0]

        # then fragment -> json_pointer
        if uri_parts.fragment:
            logger.debug(f"Following {uri_parts.fragment}")
            pointer = Pointer.from_string(uri_parts.fragment)
            target = pointer.follow_pointer(target)

        if not isinstance(target, dict):
            raise ValueError(f"Trying to dereference into a non schema target {urlunsplit(uri_parts)}")
        replace_ref_object_with_target_draft4(ref_object, target)

def ref_objects_with_scope(
    json_object: Any,
    scope: list[Any] | None=None,
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
        if id_key in json_object and json_object not in scope:
            scope.append(json_object)

        for key, value in json_object.items():
            if key not in exclude:
                yield from ref_objects_with_scope(value, scope=deepcopy(scope))
            if key == ref_key:
                yield json_object, scope
    elif isinstance(json_object, list):
        for item in json_object:
            yield from ref_objects_with_scope(item, scope=deepcopy(scope))


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
