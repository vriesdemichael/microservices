import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from math import isclose
from typing import Any, Tuple

from dataformats.jsonschema.custom_types import (
    JsonType,
    Number,
    SchemaArray,
    SchemaDict,
    SimpleTypeString,
    json_to_python_type,
)
from dataformats.jsonschema.format import (
    email_pattern,
    hostname_pattern,
    ipv4_pattern,
    ipv6_pattern,
)
from dataformats.jsonschema.json_pointer import Pointer
from dataformats.jsonschema.mixins.dereference_mixin import (
    derefence_from_above,
    dereference,
)
from rfc3986 import is_valid_uri

logger = logging.getLogger(__name__)


class MultipleValidationErrors(ValueError):
    def __init__(self, *args, errors: dict[str, list[ValueError]], json_pointer: str):
        """Raise a collection of ValueErrors at once
        Used to defer raising errors until all valueerrors are collected

        Args:
            errors: A dictionary with json pointers as keys and a list of ValueErrors
        """
        super().__init__(*args)
        self.errors = errors
        self.add_note(f"At {json_pointer}")
        self.add_note(f"With {len(errors)} errors at {list(errors.keys())}")
        self.add_note("Check the errors attribute of this exception for the specific exceptions")
        for key, values in errors.items():
            for value in values:
                self.add_note(f"{key}: {value} {value.__notes__ if hasattr(value, '__notes__') else ''}")


class CatchErrorContext:
    def __init__(self):
        self.exceptions = defaultdict(list)
        self.current_location = ""

    def at_pointer(self, json_pointer):
        self.current_location = json_pointer
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value: Exception, traceback):
        if exc_value:
            if exc_type == ValueError:
                exc_value.add_note(f"At {self.current_location}")
                self.exceptions[self.current_location].append(exc_value)
                return True
            if exc_type == MultipleValidationErrors:
                self.exceptions[self.current_location].append(exc_value)
                return True
            else:
                raise exc_value


def almost_equal_floats(value_1, value_2, delta=1e-8):
    return abs(value_1 - value_2) <= delta


def retieve_and_check_type(container: Any, name: str, types: Tuple[SimpleTypeString, ...]) -> JsonType:
    if not hasattr(container, name):
        raise ValueError(f"Cannot retrieve {name}")

    value = getattr(container, name)

    valid_python_types = tuple(json_to_python_type[t] for t in types)
    if not isinstance(value, valid_python_types):
        raise ValueError(
            f"Invalid type value {value} with type {type(value)} is not one of the valid types: {valid_python_types}"
        )
    return value


# class Draft4Validator(Draft4Dict):  # for better type hints during development
class Draft4Validator(dict):
    __all_keywords__ = (
        "id",
        "$schema",
        "title",
        "description",
        "default",
        "multipleOf",
        "maximum",
        "exclusiveMaximum",
        "minimum",
        "exclusiveMinimum",
        "maxLength",
        "minLength",
        "pattern",
        "additionalItems",
        "items",
        "maxItems",
        "minItems",
        "uniqueItems",
        "maxProperties",
        "minProperties",
        "required",
        "additionalProperties",
        "definitions",
        "properties",
        "patternProperties",
        "dependencies",
        "enum",
        "type",
        "format",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "$ref",
    )

    def __init__(self, /, __pointer__=None, **kwargs):




        if __pointer__ is None:
            __pointer__ = Pointer()
        self.pointer = __pointer__

        # derefence_from_above(current_scope=kwargs, id_key="id", ref_key="$ref", download=True, tracking_pointer=self.pointer)
        dereference(schema=self, download=True)

        for kw in self.__all_keywords__:
            kwargs.setdefault(kw, None)


        super().__init__(**kwargs)

    def _filtered(self) -> dict:
        return {key: value for key, value in self.items() if value is not None}

    def __repr__(self):
        return repr(self._filtered())

    def __str__(self):
        return str(self._filtered())

    # keywords by general instance type

    # number
    def check_multipleOf(self, value: Number):
        if (multipleOf := self["multipleOf"]) is None:
            return
        if multipleOf < 0:
            raise ValueError(f"Value must be greater than 0 (is {value})")

        mod = float(value) / float(multipleOf) % 1
        if not almost_equal_floats(mod, 0.0) and not almost_equal_floats(mod, 1.0):
            raise ValueError(f"Value is not a multiple of {multipleOf} ({value=})")

    def check_maximum(self, value: Number):
        if (maximum := self["maximum"]) is None:
            return
        either_is_float = isinstance(value, float) or isinstance(maximum, float)
        float_almost_equal = isclose(value, maximum)

        if self["exclusiveMaximum"]:
            if value >= maximum or (either_is_float and float_almost_equal):
                raise ValueError(f"Value is greater than the (exclusive) maximum ({value} >= {maximum})")
        else:
            if value > maximum:
                raise ValueError(f"Value is greater than the maximum ({value} > {maximum})")

    def check_minimum(self, value: Number):
        if (minimum := self["minimum"]) is None:
            return
        either_is_float = isinstance(value, float) or isinstance(minimum, float)
        float_almost_equal = isclose(value, minimum)
        if self["exclusiveMinimum"]:
            if value <= minimum or (either_is_float and float_almost_equal):
                raise ValueError(f"Value is smaller than the (exclusive) minimum ({value} <= {minimum})")
        else:
            if value < minimum:
                raise ValueError(f"Value is smaller than the minimum ({value} < {minimum})")

    # string
    def check_maxLength(self, value: str):
        if self["maxLength"] is not None and len(value) > self["maxLength"]:
            raise ValueError(f"Value is too long {self['maxLength']=} {len(value)=}")

    def check_minLength(self, value: str):
        if self["minLength"] is not None and len(value) < self["minLength"]:
            raise ValueError(f"Value is too short {self['minLength']=} {len(value)=}")

    def check_pattern(self, value: str):
        if self["pattern"] is not None and not re.search(self["pattern"], value):
            raise ValueError(f"Value does not match the given pattern {value=}  {self['pattern']=}")

    # array types # TODO further split up
    def check_array_container_checks(self, array: list[Any]):
        additionalItems = self["additionalItems"]
        if additionalItems is None or additionalItems is True:
            additionalItems = {}
        elif additionalItems is False:
            additionalItems = {"not": {}}  # fails against all
        items = {} if self["items"] is None else self["items"]

        if items is {} or additionalItems is {}:
            return  # These config options always yield a valid result

        subitem_errors: dict[str, list[Exception]] = defaultdict(list)
        items_is_schema = isinstance(items, dict)
        items_is_list_of_schemas = isinstance(items, list)

        if items_is_list_of_schemas and self["additionalItems"] is False and len(array) > len(items):
            msg = f"Array is larger ({len(array)=}) than the amount of items specified in the schema ({len(items)}"
            raise ValueError(msg)

        for idx, array_subitem in enumerate(array):
            pointer = self.pointer.extended_copy(str(idx))

            if items_is_schema:
                schema_for_idx = Draft4Validator(pointer, **items)
            elif idx < len(items):
                schema_for_idx = Draft4Validator(pointer, **items[idx])
            else:
                schema_for_idx = Draft4Validator(pointer, **additionalItems)

            errors = schema_for_idx.validate(array_subitem)
            if errors:
                for key, exceptions in errors.items():
                    subitem_errors[key].extend(exceptions)
        if subitem_errors:
            raise MultipleValidationErrors("Array container check failed", errors=errors, json_pointer=self.pointer)

    def check_maxItems(self, array: list[Any]):
        if self["maxItems"] is not None and len(array) > self["maxItems"]:
            raise ValueError(f"Array contains more than the maximum amount of items {self['maxItems']=} {len(array)=}")

    def check_minItems(self, array: list[Any]):
        if self["minItems"] is not None and len(array) < self["minItems"]:
            raise ValueError(f"Array contains less than the minimum amount of items {self['minItems']=} {len(array)=}")

    def check_uniqueItems(self, array: list[Any]):
        if self["uniqueItems"] is not True:
            return
        jsonified_items = [json.dumps(item, sort_keys=True) for item in array]
        seen = set()
        duplicates = [x for x in jsonified_items if x in seen or seen.add(x)]  # type: ignore

        if duplicates:
            error = ValueError("Array contains duplicates")
            duplicates_formatted = "\n\t".join(duplicates)
            error.add_note(f"Duplicates:\n\t{duplicates_formatted}")
            raise error

    # object types
    def check_maxProperties(self, dict_object: dict[str, Any]):
        if self["maxProperties"] is not None and (n_properties := len(dict_object)) > self["maxProperties"]:
            raise ValueError(f"Object exceeds maximum properties values {n_properties=} {self['maxProperties']=}")

    def check_minProperties(self, dict_object: dict[str, Any]):
        if self["minProperties"] is not None and (n_properties := len(dict_object)) < self["minProperties"]:
            raise ValueError(f"Object exceeds maximum properties values {n_properties=} {self['minProperties']=}")

    def check_required(self, dict_object: dict[str, Any]):
        if self["required"] is None:
            return
        object_keys = set(dict_object.keys())
        required_keys = set(self["required"])
        missing_keys = required_keys - object_keys
        if missing_keys:
            raise ValueError(f"Object misses the following required keys: {missing_keys}")

    def check_object_container_checks(self, dict_object: dict[str, Any]):
        properties: SchemaDict = {} if self["properties"] is None else self["properties"]
        patternProperties: SchemaDict = {} if self["patternProperties"] is None else self["patternProperties"]
        additionalProperties: SchemaDict | bool = (
            {} if self["additionalProperties"] is None else self["additionalProperties"]
        )
        if additionalProperties is True:
            additionalProperties = {}

        for object_key, object_value in dict_object.items():
            schemas_for_child: SchemaArray = []
            # step 1: add schema from properties
            if object_key in properties:
                schemas_for_child.append(properties[object_key])
            # step 2: add schemas from patternProperties
            for pattern, pattern_schema in patternProperties.items():
                if re.search(pattern, object_key):
                    schemas_for_child.append(pattern_schema)

            # step 3: add schema from additionalProperties (if and only if no schemas found so far)
            if len(schemas_for_child) == 0 and additionalProperties is not None and additionalProperties is not False:
                schemas_for_child.append(additionalProperties)

            if not schemas_for_child:
                raise ValueError(f"No suitable schemas found for suitable{self.pointer}/{object_key}")

            errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
            for schema_dict in schemas_for_child:
                schema_for_child = Draft4Validator(self.pointer.extended_copy(object_key), **schema_dict)
                child_errors = schema_for_child.validate(object_value)

                if not child_errors:
                    continue

                mve = MultipleValidationErrors(
                    f"Property {object_key} could not be validated against schema in exception note",
                    errors=child_errors,
                    json_pointer=str(self.pointer.extended_copy(object_key)),
                )
                mve.add_note(f"Schema: {schema_for_child}")
                errors[str(self.pointer.extended_copy(object_key))].append(mve)

            if errors:
                raise MultipleValidationErrors(
                    f"Could not match a valid schema for {object_key}",
                    errors=errors,
                    json_pointer=str(self.pointer.extended_copy(object_key)),
                )

    def check_dependencies(self, dict_object: dict[str, Any]):
        if self["dependencies"] is None:
            return
        exceptions = defaultdict(list)
        for dependency, dependency_value in self["dependencies"].items():
            if dependency not in dict_object:
                continue  # nothing to check against

            if isinstance(dependency_value, list):
                for dependant_field in dependency_value:
                    if dependant_field not in dict_object:
                        exceptions[f"''/{dependency}"].append(
                            ValueError(f"Missing key {dependant_field} as dependency for {dependency}")
                        )
            elif isinstance(dependency_value, dict):
                dependency_schema = Draft4Validator(
                    self.pointer.extended_copy("dependencies"), **dependency_value
                )
                errors = dependency_schema.validate(dict_object)
                if errors:
                    mve = MultipleValidationErrors(
                        f"Dependecy check for object key {dependency} failed",
                        errors=errors,
                        json_pointer=f"''/{dependency}",
                    )
                    exceptions[f"''/{dependency}"].append(mve)
        if exceptions:
            raise MultipleValidationErrors("Failed dependencies found", errors=exceptions, json_pointer="")

    # for any instance type
    def check_enum(self, value: Any):
        try:
            if self["enum"] is None:
                return
        except KeyError as e:
            raise RuntimeError(self.pointer) from e
        for enum_value in self["enum"]:
            if type(enum_value) != type(value) and (isinstance(enum_value, bool) or isinstance(value, bool)):
                # special case bool <> numeric
                continue
            if isinstance(enum_value, bool):
                # special case bool
                if value is enum_value:
                    return
            elif isinstance(enum_value, (int, float)) and isinstance(value, (int, float)):
                # special case numeric
                if isclose(float(enum_value), float(value)):
                    return
            elif enum_value == value:
                return

        raise ValueError(f"Value {value} is not one of the given enums {self['enum']}")

    def check_type(self, value: Any):
        if self["type"] is None:
            return
        types = [self["type"]] if isinstance(self["type"], str) else self["type"]

        for valid_type in types:
            if valid_type == "null" and value is None:
                return
            elif valid_type == "boolean" and (value is True or value is False):
                return
            elif isinstance(value, json_to_python_type[valid_type]):
                if isinstance(value, bool) and valid_type != "boolean":
                    continue  # special case: bool is not numeric
                return

        raise ValueError(f"Type of value {value} is not one of {types}")

    def check_allOf(self, any_obj: Any):
        if self["allOf"] is None:
            return
        errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
        for idx, schema in enumerate(self["allOf"]):
            schema_errors = Draft4Validator(
                self.pointer.extended_copy("allOf").extended_copy(str(idx)), **schema
            ).validate(any_obj)
            for schema_pointer, error_list in schema_errors.items():
                errors[schema_pointer].extend(error_list)
        if errors:
            raise MultipleValidationErrors(
                "Could not validate against schemas for the given allOf", errors=errors, json_pointer=""
            )

    def check_anyOf(self, any_obj):
        if self["anyOf"] is None:
            return
        errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
        for idx, schema in enumerate(self["anyOf"]):
            schema_errors = Draft4Validator(
                self.pointer.extended_copy("anyOf").extended_copy(str(idx)), **schema
            ).validate(any_obj)
            if not schema_errors:
                return  # and forget about all other errors
            else:
                for schema_pointer, error_list in schema_errors.items():
                    errors[schema_pointer].extend(error_list)

        if errors:
            raise MultipleValidationErrors(
                "Could not validate against schemas for the given anyOf", errors=errors, json_pointer=""
            )

    def check_oneOf(self, any_obj: Any):
        if self["oneOf"] is None:
            return
        valid_schemas: list[int] = []
        errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
        for idx, schema in enumerate(self["oneOf"]):
            schema_errors = Draft4Validator(
                self.pointer.extended_copy("oneOf").extended_copy(str(idx)), **schema
            ).validate(any_obj)

            if not schema_errors:
                valid_schemas.append(idx)
            else:
                for schema_pointer, error_list in schema_errors.items():
                    errors[schema_pointer].extend(error_list)

        if len(valid_schemas) == 0:
            raise MultipleValidationErrors(
                "Could not validate against schemas for the given oneOf, no schema matched",
                errors=errors,
                json_pointer="",
            )

        elif len(valid_schemas) >= 2:
            raise ValueError(
                f"Could not validate gainst the schema of the given oneOf, multiple schemas matched (at indices {valid_schemas})",
            )

    def check_not(self, any_obj: Any):
        if self["not"] is not None:
            errors = Draft4Validator(self.pointer.extended_copy("not"), **self["not"]).validate(any_obj)
            if not errors:
                raise ValueError("Validation for not keyword failed, instance is valid for the given schema")

    def check_format(self, value: str):
        match (self["format"]):
            case "date-time":
                try:
                    datetime.fromisoformat(value)
                except ValueError as e:
                    e.add_note(f"Value {value} is not a valid date-format string")
                    raise
            case "email":
                if not email_pattern.match(value):
                    raise ValueError(f"Value {value} is not a valid email string")
            case "hostname":
                if not hostname_pattern.match(value):
                    raise ValueError(f"Value {value} is not a valid hostname string")
            case "ipv4":
                if not ipv4_pattern.match(value):
                    raise ValueError(f"Value {value} is not a valid ipv4 formatted string")
            case "ipv6":
                if not ipv6_pattern.match(value):
                    raise ValueError(f"Value {value} is not a valid ipv4 formatted string")
            case "uri":
                if not is_valid_uri(value):
                    raise ValueError(f"Value {value} is not a valid uri")
            case "regex":
                try:
                    _ = re.compile(value)
                except re.error as e:
                    e.add_note(f"Value {value} is not a valid regex pattern")
            case None:
                return
            case _:
                raise RuntimeError(f"Received an unsupported format keyword: {self['format']}")

    def check_metaschema(self, download_external: bool):
        # TODO fix recursion
        if self["$schema"] and "http://json-schema.org/draft-04/schema" not in self["$schema"]:
            metaschema = Draft4Validator(self.pointer.extended_copy("$schema"), **{"$ref": self["$schema"]})
        else:
            metaschema = Draft4Validator(self.pointer.extended_copy("$schema"))
        errors = metaschema.validate(self)
        if errors:
            raise MultipleValidationErrors(
                "The schema for validation is not valid against its own metaschema (set in $schema or draft4 when missing)",
                errors=errors,
                json_pointer="",
            )

    def derefence(self):
        if self.pointer != Pointer():
            logger.info("No deref because not top level")
            return  # only deref the top level
        derefence_from_above(current_scope=self, id_key="id", ref_key="$ref", download=True, tracking_pointer=self.pointer)

    def validate(self, instance: Any) -> dict[str, list[ValueError | MultipleValidationErrors]]:
        # logger.debug(f"Starting validation for '{str()}'")
        # reentrant context manager which collects a single exception per `with` statement
        error_collector = CatchErrorContext()

        # self.derefence()

        # TODO find all exceptions before returning
        try:
            # Any types
            # self.check_metaschema(instance) # TODO fix recursion
            self.check_type(instance)
            self.check_enum(instance)
            self.check_allOf(instance)
            self.check_anyOf(instance)
            self.check_oneOf(instance)
            self.check_not(instance)

            # object
            if isinstance(instance, dict):
                self.check_maxProperties(instance)
                self.check_minProperties(instance)
                self.check_required(instance)
                self.check_dependencies(instance)
                self.check_object_container_checks(instance)

            # array
            if isinstance(instance, list):
                self.check_array_container_checks(instance)
                self.check_uniqueItems(instance)
                self.check_minItems(instance)
                self.check_maxItems(instance)

            # string
            if isinstance(instance, str):
                self.check_maxLength(instance)
                self.check_minLength(instance)
                self.check_pattern(instance)

            # number
            if isinstance(instance, (int, float)):
                self.check_multipleOf(instance)
                self.check_minimum(instance)
                self.check_maximum(instance)
        except ValueError as e:
            return {"non lazy": [e]}

        return error_collector.exceptions
