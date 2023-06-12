# TODO base uri changesobjects_with_id
import json
from logging import getLogger
from pathlib import Path
from typing import Iterable
from urllib.parse import ParseResult, urldefrag, urljoin, urlparse
from urllib.request import url2pathname

import requests
from dataformats.jsonschema.custom_types import (
    JsonType,
    SchemaType,
)
from dataformats.jsonschema.json_pointer import Pointer
from dataformats.jsonschema.mixins.schema_parsing import (
    absolute_id_map,
    ref_map,
)
from rfc3986 import URIReference

logger = getLogger("dereference")


# def objects_with_id(
#     json_object: JsonType,
#     id_key: str,
# ) -> SchemaDict:
#     if not isinstance(json_object, dict):
#         raise ValueError("Cannot find ids in an objects that is not a dictionary")
#     schema_mapping = find_schemas(json_object)
#     id_schema_mapping = {k: v for k, v in schema_mapping.items() if id_key in v}
#     id_schema_only_string_mappings = {
#         id_value: v for v in id_schema_mapping.values() if isinstance(id_value := v[id_key], str)
#     }

#     return id_schema_only_string_mappings


# def has_ref(instance: JsonType, ref_key="$ref") -> str | None:
#     if not isinstance(instance, dict):
#         return None
#     ref = instance.get(ref_key, None)
#     if ref:
#         return str(ref)
#     else:
#         return None


# # TODO top level without id?
# def determine_baseuri_from_scopes(scopes: SchemaArray, id_key="id") -> tuple[str, SchemaType] | tuple[None, SchemaType]:
#     relative_path = ""
#     target_scope = None
#     for scope in scopes[::-1]:  # reverse since the last once is the most direct parent
#         if (id_value := scope.get(id_key, None)) is not None and isinstance(id_value, str):
#             # most direct parent with id keyword is where pointers shuld be resolved
#             if target_scope is None:
#                 target_scope = scope
#             parts: ParseResult = urlparse(id_value)
#             if parts.scheme:
#                 if relative_path:
#                     # redundant slashes for consistent behaviour of urljoin
#                     absolute_id_of_most_direct_parent = urljoin(f"{scope[id_key]}/", f"../{relative_path}")
#                 else:
#                     return id_value, target_scope
#                 return absolute_id_of_most_direct_parent, target_scope
#             else:
#                 relative_path = urljoin(f"{relative_path}/", f"../{scope[id_key]}")

#     return None, scopes[0]


def analyze_ref(ref: str, base_uri: str | None) -> tuple[str | None, str | None]:
    normalized_uri = URIReference.from_string(ref).normalize().unsplit()
    uri_parts: ParseResult = urlparse(normalized_uri)

    is_absolute = uri_parts.scheme or uri_parts.hostname
    is_relative = uri_parts.hostname or uri_parts.path
    absolute_uri = None

    if is_absolute:
        absolute_uri = uri_parts.geturl()
    elif is_relative:
        if base_uri:
            absolute_uri = urljoin(f"{base_uri}/", f"../{uri_parts.path}")
    if absolute_uri:
        absolute_uri, _ = urldefrag(absolute_uri)

    return absolute_uri, uri_parts.fragment


# TODO split up and park in a better place
def retrieve_schema(uri, download: bool) -> SchemaType:
    uri_parts: ParseResult = urlparse(uri)
    logger.debug(f"{uri_parts=}")
    if uri_parts.scheme == "file":
        return json.loads(Path(url2pathname(uri_parts.path)).read_text())
    elif uri_parts.scheme.startswith("http"):
        if download:
            response = requests.get(uri)
            response.raise_for_status()
            return response.json()
        else:
            return {}
    else:
        raise ValueError(f"Encountered a ref with a unsupported scheme ({uri_parts.scheme})")


# def get_target_ref_for(*, ref: str, scopes: SchemaArray, download: bool, id_key) -> SchemaType:
#     if not scopes:
#         raise ValueError("No scopes given")

#     # inline references first
#     # TODO not sure if this should be from most direct scope parent or the root object
#     # TODO make ids complete with base uri?
#     location_independant_ref_targets = objects_with_id(scopes[0], id_key=id_key)
#     if ref in location_independant_ref_targets:
#         logger.info(f"Found inline ref target for {ref}")
#         return location_independant_ref_targets[ref]

#     # canonical second
#     base_uri, base_schema = determine_baseuri_from_scopes(scopes=scopes, id_key=id_key)
#     absolute_uri, fragment = analyze_ref(ref, base_uri)

#     if absolute_uri:
#         target = retrieve_schema(absolute_uri, download)
#     else:
#         target = base_schema

#     if fragment:
#         pointer = Pointer.from_string(fragment)
#         try:
#             resolved_target = pointer.follow_pointer(target)
#             if not isinstance(resolved_target, dict):
#                 raise ValueError(f"Trying to derefence into a non schema object at {ref}")
#             return resolved_target
#         except (KeyError, AttributeError, ValueError) as e:
#             print(e)
#             raise ValueError(
#                 f"{base_uri=} {base_schema=} {absolute_uri=} {fragment=} {pointer=} {target=} {scopes=}"
#             ) from e

#     else:
#         return target


def replace_schema_in_place(old_schema: SchemaType, new_schema: SchemaType):
    for key in list(old_schema.keys()):
        old_schema.pop(key)
    old_schema.update(new_schema)


# # TODO deal with infinite recursion
# def derefence_from_above(
#     *,
#     current_scope: JsonType,
#     download: bool,
#     id_key: str,
#     ref_key: str,
#     scopes: SchemaArray | None = None,
#     tracking_pointer: Pointer | None = None,
#     exclude: Iterable[str] = ("enum", "default"),
# ):
#     if not tracking_pointer:
#         tracking_pointer = Pointer()

#     if not scopes:
#         scopes = []
#     else:
#         scopes = scopes.copy()
#     if current_scope in scopes:
#         return  # recursive pattern
#     if isinstance(current_scope, dict):
#         scopes.append(current_scope)

#     if isinstance(current_scope, list):
#         for idx in range(len(current_scope)):
#             idx_tracking_pointer = tracking_pointer = tracking_pointer.extended_copy(str(idx))
#             while ref := has_ref(current_scope[idx], ref_key=ref_key):
#                 logger.info(f"Deref at {idx_tracking_pointer} of {ref}")
#                 current_scope[idx] = get_target_ref_for(ref=ref, scopes=scopes, download=download, id_key=id_key)
#             derefence_from_above(
#                 current_scope=current_scope[idx],
#                 id_key=id_key,
#                 ref_key=ref_key,
#                 download=download,
#                 scopes=scopes,
#                 tracking_pointer=idx_tracking_pointer,
#             )
#         # logger.info(f"Done with {tracking_pointer}")
#     elif isinstance(current_scope, dict):
#         # special case: ref in top level or previously derefenced object
#         while (ref := has_ref(current_scope)) is not None:
#             logger.info(f"INPLACE deref at {tracking_pointer} of {ref}")
#             target_schema = get_target_ref_for(ref=ref, scopes=scopes, download=download, id_key=id_key)
#             replace_schema_in_place(current_scope, target_schema)

#         for key in list(current_scope.keys()):
#             if key in exclude:
#                 continue
#             key_tracking_pointer = tracking_pointer.extended_copy(key)
#             while ref := has_ref(current_scope[key]):
#                 logger.info(f"Deref at {key_tracking_pointer} of {ref}")

#                 current_scope[key] = get_target_ref_for(ref=ref, scopes=scopes, download=download, id_key=id_key)
#             if current_scope[key] not in scopes:
#                 derefence_from_above(
#                     current_scope=current_scope[key],
#                     id_key=id_key,
#                     ref_key=ref_key,
#                     download=download,
#                     scopes=scopes,
#                     tracking_pointer=key_tracking_pointer,
#                 )
#     else:
#         return

###############
## ATTEMPT 3 ##
###############
def get_target_for_ref(top_level_schema: SchemaType, ref: str, ref_pointer: Pointer, absolute_ids: dict[Pointer, str], download: bool) -> SchemaType:
    parent_pointers: list[Pointer] = [x for x in absolute_ids.keys() if ref_pointer.is_child_of(x)]
    parent_pointers.sort(key=len)
    if not parent_pointers:
        raise ValueError(f"Cannot determine the base uri of ref {ref=} because it has no parents with id key specified")
    ref_base_uri = absolute_ids[parent_pointers[-1]]

    absolute_id_to_schema: dict[str, JsonType] = {id_val: pointer.follow_pointer(top_level_schema) for pointer, id_val in absolute_ids.items()}
    absolute_uri, fragment = analyze_ref(ref, ref_base_uri)
    if absolute_uri is None:
        raise RuntimeError("You should have an absolute uri here")
    if absolute_uri in absolute_ids.values():
        target_schema = absolute_id_to_schema[absolute_uri]
    else:
        target_schema = retrieve_schema(absolute_uri, download=download)
        dereference(schema=target_schema, download=download)  # TODO two or more schemas referencing eachother bounce infinitely # TODO more parms from dereference

    if fragment:
        resolved_pointer = Pointer.from_string(fragment).follow_pointer(target_schema)
    else:
        resolved_pointer = target_schema

    if not isinstance(resolved_pointer, dict):
        raise ValueError("Ref is not a schema ")
        # TODO might have to walk up and down again when multiple of the same uri are available (though they should be the same)
    return resolved_pointer

def dereference(
    *,
    schema: SchemaType,
    download: bool,

    absolute_ids: dict[Pointer, str] | None = None,

    id_key: str = "id",
    ref_key: str = "$ref",
    exclude: Iterable[str] = ("enum", "default"),
):

    if absolute_ids is None:
        absolute_ids = absolute_id_map(schema, id_key=id_key)

    refs = ref_map(schema, ref_key=ref_key, exclude=exclude)
    while refs and (ref_pointer := next(iter(refs))):
        ref: str = refs[ref_pointer]  # type: ignore
        target_schema = get_target_for_ref(top_level_schema=schema, ref=ref, ref_pointer=ref_pointer, absolute_ids=absolute_ids, download=download)


        # in place replacement for $ref at top level
        if len(ref_pointer) == 0:
            replace_schema_in_place(schema, target_schema)
            dereference(schema=schema, download=download)  # ugly :(
            return

        ref_parent = ref_pointer.parent.follow_pointer(schema)
        key_or_index = ref_pointer.parts[-1]
        if isinstance(ref_parent, list):
            ref_parent[int(key_or_index)] = target_schema
        elif isinstance(ref_parent, dict):
            ref_parent[key_or_index] = target_schema
        else:
            raise RuntimeError(f"ref parent is not a container type {ref_parent=} {key_or_index=}")
