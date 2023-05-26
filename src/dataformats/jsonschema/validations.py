import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from math import isclose
from typing import Any

from dataformats.jsonschema.custom_types import (
    Number,
    SimpleTypeString,
    Unset,
    json_to_python_type,
    unset_value,
)
from dataformats.jsonschema.format import (
    email_pattern,
    hostname_pattern,
    ipv4_pattern,
    ipv6_pattern,
)
from dataformats.jsonschema.model import Draft4MetaSchema
from rfc3986 import is_valid_uri  # TODO can this be regex too?logger.debug

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


# keywords by general instance type


def almost_equal_floats(value_1, value_2, delta=1e-8):
    return abs(value_1 - value_2) <= delta


# number
def multipleOf(value: Number, multipleOf: Number):
    """5.1.2.2 A numeric instance is valid against "multipleOf" if the result of the division of the instance by this keyword's value is an integer."""
    if value < 0:
        raise ValueError(f"Value must be greater than 0 (is {value})")

    mod = float(value) / float(multipleOf) % 1
    if not almost_equal_floats(mod, 0.0) and not almost_equal_floats(mod, 1.0):
        raise ValueError(f"Value is not a multiple of {multipleOf} ({value=})")


def maximum(value: Number, maximum: Number, exclusiveMaximum=False):
    either_is_float = isinstance(value, float) or isinstance(maximum, float)
    float_almost_equal = isclose(value, maximum)

    if exclusiveMaximum:
        if value >= maximum or (either_is_float and float_almost_equal):
            raise ValueError(f"Value is greater than the (exclusive) maximum ({value} >= {maximum})")
    else:
        if value > maximum:
            raise ValueError(f"Value is greater than the maximum ({value} > {maximum})")


def minimum(value: Number, minimum: Number, exclusiveMinimum=False):
    either_is_float = isinstance(value, float) or isinstance(minimum, float)
    float_almost_equal = isclose(value, minimum)
    if exclusiveMinimum:
        if value <= minimum or (either_is_float and float_almost_equal):
            raise ValueError(f"Value is smaller than the (exclusive) minimum ({value} <= {minimum})")
    else:
        if value < minimum:
            raise ValueError(f"Value is smaller than the minimum ({value} < {minimum})")


# string
def maxLength(value: str, maxLength: int):
    if len(value) > maxLength:
        raise ValueError(f"Value is too long {maxLength=} {len(value)=}")


def minLength(value: str, minLength: int = 0):
    if len(value) < minLength:
        raise ValueError(f"Value is too short {minLength=} {len(value)=}")


def pattern(value: str, pattern: str):
    if not re.search(pattern, value):
        raise ValueError(f"Value does not match the given pattern {value=}  {pattern=}")


# array types
def array_container_checks(
    array: list[Any],
    json_pointer: str,
    items: list[Draft4MetaSchema] | Draft4MetaSchema | Unset = unset_value,
    additionalItems: bool | Draft4MetaSchema | Unset = unset_value,
):
    # TODO triple check items as unset_value
    if additionalItems == unset_value:
        additionalItems = True
    if items == unset_value or additionalItems is True:
        return  # These config options always yield a valid result

    subitem_errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
    if isinstance(items, Draft4MetaSchema):
        for idx, array_subitem in enumerate(array):
            errors = validate(array_subitem, schema=items)
            if errors:
                if additionalItems is not False:
                    additional_items_errors = validate(array_subitem, schema=items)
                    if additional_items_errors:
                        errors.update(additional_items_errors)
                        e = MultipleValidationErrors(
                            "Array item could not be validated against the items schema or the additionalItems schema",
                            errors=errors,
                            json_pointer=f"{json_pointer}/{idx}",
                        )
                        subitem_errors[f"{json_pointer}/{idx}"].append(e)
                else:
                    e = MultipleValidationErrors(
                        "Array item could not be validated against the items schema",
                        errors=errors,
                        json_pointer=f"{json_pointer}/{idx}",
                    )
                    subitem_errors[f"{json_pointer}/{idx}"].append(e)

    elif isinstance(items, list):
        if additionalItems is False and len(array) > len(items):
            raise ValueError(
                f"Array is larger ({len(array)=}) than the amount of items specified in the schema (schema has {len(items)} items)"
            )

        for idx, array_subitem in enumerate(array):
            if idx < len(items):
                errors = validate(array_subitem, schema=items[idx])
                if errors:
                    e = MultipleValidationErrors(
                        "Array item could not be validated against it schema",
                        errors=errors,
                        json_pointer=f"{json_pointer}/{idx}",
                    )
                    subitem_errors[f"{json_pointer}/{idx}"].append(e)
            elif isinstance(additionalItems, Draft4MetaSchema):
                errors = validate(array_subitem, additionalItems)
                if errors:
                    e = MultipleValidationErrors(
                        "Array item could not be validated against the additionalItems schema",
                        errors=errors,
                        json_pointer=f"{json_pointer}/{idx}",
                    )
                    subitem_errors[f"{json_pointer}/{idx}"].append(e)
            else:
                raise RuntimeError("Flawed logic, if you reach this point it is a bug")

    if subitem_errors:
        raise MultipleValidationErrors(
            f"Multiple validation errors at {json_pointer}", errors=subitem_errors, json_pointer=json_pointer
        )


def maxItems(array: list[Any], maxItems: int):
    if len(array) > maxItems:
        raise ValueError(f"Array contains more than the maximum amount of items {maxItems=} {len(array)=}")


def minItems(array: list[Any], minItems: int):
    if len(array) < minItems:
        raise ValueError(f"Array contains less than the minimum amount of items {minItems=} {len(array)=}")


def uniqueItems(array: list[Any]):
    jsonified_items = [json.dumps(item, sort_keys=True) for item in array]
    seen = set()
    duplicates = [x for x in jsonified_items if x in seen or seen.add(x)]  # type: ignore

    if duplicates:
        error = ValueError("Array contains duplicates")
        duplicates_formatted = "\n\t".join(duplicates)
        error.add_note(f"Duplicates:\n\t{duplicates_formatted}")
        raise error


# object types
def maxProperties(dict_object: dict[str, Any], maxProperties: int):
    if (n_properties := len(dict_object)) > maxProperties:
        raise ValueError(f"Object exceeds maximum properties values {n_properties=} {maxProperties=}")


def minProperties(dict_object: dict[str, Any], minProperties: int):
    if (n_properties := len(dict_object)) < minProperties:
        raise ValueError(f"Object exceeds maximum properties values {n_properties=} {minProperties=}")


def required(dict_object: dict[str, Any], required: list[str]):
    object_keys = set(dict_object.keys())
    required_keys = set(required)
    missing_keys = required_keys - object_keys
    if missing_keys:
        raise ValueError(f"Object misses the following required keys: {missing_keys}")


def object_container_checks(
    dict_object: dict[str, Any],
    properties: dict[str, Draft4MetaSchema] | Unset,
    additionalProperties: bool | Draft4MetaSchema | Unset,
    patternProperties: dict[str, Draft4MetaSchema] | Unset,
    json_pointer: str,
):
    if properties == unset_value:
        properties = {}
    if patternProperties == unset_value:
        patternProperties = {}
    if additionalProperties == unset_value or additionalProperties is True:
        additionalProperties = Draft4MetaSchema()

    for object_key, object_value in dict_object.items():
        schemas_for_child: list[Draft4MetaSchema] = []
        if properties_schema := properties.get(object_key, None):
            schemas_for_child.append(properties_schema)
        for pattern, pattern_schema in patternProperties.items():
            if re.search(pattern, object_key):
                schemas_for_child.append(pattern_schema)
        if len(schemas_for_child) == 0 and additionalProperties:
            schemas_for_child.append(additionalProperties)

        if not schemas_for_child:
            e = ValueError(f"No schema suitable for {object_key=}")
            e.add_note(f"At {json_pointer}/{object_key}")
            raise e

        # TODO store origin of schema (jsonpointer) for better logging
        errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
        for schema_for_child in schemas_for_child:
            child_errors = validate(object_value, schema_for_child)

            if not child_errors:
                continue

            schema_title = schema_for_child.title if schema_for_child.title != unset_value else "undefined"
            mve = MultipleValidationErrors(
                f"property {object_key} could not be validated with {schema_title=}",
                errors=child_errors,
                json_pointer=f"{json_pointer}/{object_key}",
            )
            errors[f"{json_pointer}/{object_key}"].append(mve)

        if errors:
            raise MultipleValidationErrors(
                f"Could not match a valid schema for {object_key}",
                errors=errors,
                json_pointer=f"{json_pointer}/{object_key}",
            )


def dependencies(dict_object: dict[str, Any], dependencies: dict[str, list[str] | Draft4MetaSchema], json_pointer: str):
    exceptions = defaultdict(list)
    for dependency, dependency_value in dependencies.items():
        if dependency not in dict_object:
            continue  # nothing to check against

        if isinstance(dependency_value, list):
            for dependant_field in dependency_value:
                if dependant_field not in dict_object:
                    exceptions[f"{json_pointer}/{dependency}"].append(
                        ValueError(f"Missing key {dependant_field} as dependency for {dependency}")
                    )
        elif isinstance(dependency_value, Draft4MetaSchema):
            errors = validate(dict_object, dependency_value)
            if errors:
                mve = MultipleValidationErrors(
                    f"Dependecy check for object key {dependency} failed",
                    errors=errors,
                    json_pointer=f"{json_pointer}/{dependency}",
                )
                exceptions[f"{json_pointer}/{dependency}"].append(mve)
    if exceptions:
        raise MultipleValidationErrors("Failed dependencies found", errors=exceptions, json_pointer=json_pointer)


# for any instance type
def enum(value: Any, enum_values: tuple[Any, ...]):
    for enum_value in enum_values:
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

    raise ValueError(f"Value {value} is not one of the given enums {enum_values}")


def type_(value: Any, type_: SimpleTypeString | list[SimpleTypeString]):
    types = [type_] if isinstance(type_, str) else type_

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


def allOf(any_obj: Any, allOf: list[Draft4MetaSchema], json_pointer: str):
    errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
    for schema in allOf:
        schema_errors = validate(any_obj, schema)
        for schema_pointer, error_list in schema_errors.items():
            errors[schema_pointer].extend(error_list)
    if errors:
        raise MultipleValidationErrors(
            "Could not validate against schemas for the given allOf", errors=errors, json_pointer=json_pointer
        )


def anyOf(any_obj, anyOf: list[Draft4MetaSchema], json_pointer: str):
    errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
    for schema in anyOf:
        schema_errors = validate(any_obj, schema)

        if not schema_errors:
            return  # and forget about all other errors
        else:
            for schema_pointer, error_list in schema_errors.items():
                errors[schema_pointer].extend(error_list)

    if errors:
        raise MultipleValidationErrors(
            "Could not validate against schemas for the given anyOf", errors=errors, json_pointer=json_pointer
        )


def oneOf(any_obj, oneOf: list[Draft4MetaSchema], json_pointer):
    valid_schemas: list[int] = []
    errors: dict[str, list[ValueError | MultipleValidationErrors]] = defaultdict(list)
    for idx, schema in enumerate(oneOf):
        schema_errors = validate(any_obj, schema)
        if not schema_errors:
            valid_schemas.append(idx)
        else:
            for schema_pointer, error_list in schema_errors.items():
                errors[schema_pointer].extend(error_list)

    if len(valid_schemas) == 0:
        raise MultipleValidationErrors(
            "Could not validate against schemas for the given oneOf, no schema matched",
            errors=errors,
            json_pointer=json_pointer,
        )

    elif len(valid_schemas) >= 2:
        e = ValueError(
            f"Could not validate gainst the schema of the given oneOf, multiple schemas matched (at indices {valid_schemas})",
        )
        e.add_note(f"At {json_pointer}")
        raise e


def not_(any_obj, not_):
    errors = validate(any_obj, not_)
    if not errors:
        raise ValueError("Validation for not keyword failed, instance is valid for the given schema")


def format(value: str, format):
    match (format):
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
        case _:
            raise RuntimeError(f"Received an unsupported format keyword: {format}")


def resolve_metaschema(schema: Draft4MetaSchema, download_external: bool, json_pointer: str):
    if "http://json-schema.org/draft-04/schema" not in schema.schema_:
        metaschema = Draft4MetaSchema(ref_=schema.schema_)
    else:
        metaschema = Draft4MetaSchema()
    errors = validate(metaschema, schema)
    if errors:
        raise MultipleValidationErrors(
            "The schema for validation is not valid against its own metaschema (set in $schema or draft4 when missing)",
            errors=errors,
            json_pointer=json_pointer,
        )


# TODO download external is not consistently passed, set it here like this for now
download_external=True

def validate(instance: Any, schema: Draft4MetaSchema, ) -> dict[str, list[ValueError | MultipleValidationErrors]]:

    logger.debug(f"Starting validation for '{schema.json_pointer}'")
    # reentrant context manager which collects a single exception per `with` statement
    error_collector = CatchErrorContext()
    if not isinstance(schema, Draft4MetaSchema):
        raise ValueError(f"The given schema is not a parsed Draft4 schema {type(schema)=}")

    if schema.schema_ != unset_value:
        resolve_metaschema(schema, download_external, schema.json_pointer)

    if schema.type != unset_value:
        with error_collector.at_pointer(schema.json_pointer):
            type_(instance, schema.type)

    if schema.enum != unset_value:
        with error_collector.at_pointer(schema.json_pointer):
            enum(instance, schema.enum)

    if schema.allOf != unset_value:
        with error_collector.at_pointer(schema.json_pointer):
            allOf(instance, schema.allOf, schema.json_pointer)

    if schema.anyOf != unset_value:
        with error_collector.at_pointer(schema.json_pointer):
            anyOf(instance, schema.anyOf, schema.json_pointer)

    if schema.oneOf != unset_value:
        with error_collector.at_pointer(schema.json_pointer):
            oneOf(instance, schema.oneOf, schema.json_pointer)

    if schema.not_ != unset_value:
        with error_collector.at_pointer(schema.json_pointer):
            not_(instance, schema.not_)

    if isinstance(instance, dict):
        if schema.maxProperties != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                maxProperties(instance, schema.maxProperties)

        if schema.minProperties != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                minProperties(instance, schema.minProperties)

        if schema.required != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                required(instance, schema.required)

        if schema.dependencies != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                dependencies(instance, schema.dependencies, schema.json_pointer)  # type ignore

        with error_collector.at_pointer(schema.json_pointer):
            object_container_checks(
                dict_object=instance,
                properties=schema.properties,  # type: ignore
                additionalProperties=schema.additionalProperties,
                patternProperties=schema.patternProperties,  # type: ignore
                json_pointer=schema.json_pointer,
            )

    elif isinstance(instance, list):
        with error_collector.at_pointer(schema.json_pointer):
            array_container_checks(
                instance,
                json_pointer=schema.json_pointer,
                items=schema.items,
                additionalItems=schema.additionalItems,
            )

        if schema.uniqueItems is True:
            with error_collector.at_pointer(schema.json_pointer):
                uniqueItems(instance)

        if schema.minItems != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                minItems(instance, schema.minItems)
        if schema.maxItems != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                maxItems(instance, schema.maxItems)

    elif isinstance(instance, str):
        if schema.maxLength != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                maxLength(instance, schema.maxLength)
        if schema.minLength != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                minLength(instance, schema.minLength)
        if schema.pattern != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                pattern(instance, schema.pattern)

    elif isinstance(instance, Number):
        if schema.multipleOf != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                multipleOf(instance, schema.multipleOf)
        if schema.maximum != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                if schema.exclusiveMaximum != unset_value:
                    maximum(instance, schema.maximum, schema.exclusiveMaximum)
                else:
                    maximum(instance, schema.maximum)
        if schema.minimum != unset_value:
            with error_collector.at_pointer(schema.json_pointer):
                if schema.exclusiveMinimum != unset_value:
                    minimum(instance, schema.minimum, schema.exclusiveMinimum)
                else:
                    minimum(instance, schema.minimum)

    # elif isinstance(instance, bool):
    #     pass
    # elif instance is None:
    #     pass

    return error_collector.exceptions
