from typing import Any, Generator

from dataformats.jsonschema.json_pointer import Pointer

SchemaType = dict[str, Any]



def normalize_ref(ref: str) -> str:
    # TODO normalize ref function
    return ref

def replace_ref_object_with_target_draft4(ref_object: SchemaType, target_object: SchemaType):
    """Draft 4 specific replace ref"""
    for key in ref_object:
        ref_object.pop(key)
    ref_object.update(target_object)
    return ref_object


def dereference(json_object, download=True, id_key="id", ref_key="$ref"):
    # id_references = objects_with_id(json_object)
    for ref_object, scope_list in ref_objects_with_scope(json_object):
        # Check for inline references by id first
        id_objects_top_level_scope = objects_with_id(scope_list[0])
        for id_object in id_objects_top_level_scope:
            if id_object[id_key]:
                replace_ref_object_with_target_draft4(ref_object, id_object)
                return ref_object

        # then canonical
        normalized_ref = normalize_ref(ref_object["$ref"])
        external_part, fragment = normalized_ref.split("#")
        target = None

        if external_part:
            # Determine absolute version first
            uri_is_absolute = normalized_ref.startswith(("https://", "http://", "file://"))
            if uri_is_absolute:
                pass
            else:
                # Find parent with absolute uri
                # TODO uri object, this is too much effort
                # TODO scope changes
                pass
            target = None

        if fragment:
            pass
            pointer = Pointer.from_string(fragment)
            target = pointer.follow_pointer(target)

        if not isinstance(target, dict):
            # TODO specialized exception in which the json_object, scope, ref are stored
            raise ValueError(f"Trying to dereference into a non schema target {normalized_ref}")
        for key in ref_object:
            # draft 4 -> ignore all sibling keywords :(
            ref_object.pop(key)
        ref_object.update(target)


def ref_objects_with_scope(
    json_object: Any, scope: list[Any] | None=None
) -> Generator[tuple[SchemaType, list[SchemaType]], None, None]:
    """_summary_

    Args:
        json_object: The object to  find refs in
        scope: The known scope for the object,
               the first in the list is the parent scope, the last is
               the most direct parent with a base uri. Defaults to None.

    Yields:
        A tuple of object with $ref key, list of parent scopes
    """
    if scope is None:
        scope = []
        scope.append(json_object)

    if isinstance(json_object, dict):
        if "id" in json_object:
            scope.append(json_object)

        for key, value in json_object.items():
            if key not in ("default", "enum"):
                yield from ref_objects_with_scope(value)
            if key == "$ref":
                yield json_object, scope
    elif isinstance(json_object, list):
        for item in json_object:
            yield from ref_objects_with_scope(item)


def objects_with_id(json_object: Any) -> Generator[Any, None, None]:
    # descend into everything but 'default' and 'enum'
    if isinstance(json_object, dict):
        for key, value in json_object.items():
            if key not in ("default", "enum"):
                yield from objects_with_id(value)
            if key == "id":
                yield json_object
    elif isinstance(json_object, list):
        for item in json_object:
            yield from objects_with_id(item)
    else:
        pass
