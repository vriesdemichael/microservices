from typing import Any, Literal, Type, TypeAlias

Number: TypeAlias = int | float
SimpleTypeString = Literal["array", "boolean", "integer", "null", "number", "object", "string"]
python_types = Type[list | bool | dict[str, Any] | str | Number | dict | None]
json_to_python_type: dict[str, python_types] = {
    "array": list,
    "boolean": bool,
    "integer": int,
    "number": Number,  # type: ignore[dict-item]
    "object": dict,
    "string": str,
    "null": type(None),
}

Array: TypeAlias = list['JsonType']
Object: TypeAlias = dict[str, 'JsonType']

JsonType: TypeAlias = str | bool | Number | Array | Object | None

SchemaType: TypeAlias = dict[str, JsonType]
SchemaArray: TypeAlias = list[SchemaType]
SchemaDict: TypeAlias = dict[str, SchemaType]

_test_JsonType: JsonType = {"some": {"nested": [{"structure": 2}]}}
_test_SchemaType: SchemaType = {"just": "a", "dict": 2}
