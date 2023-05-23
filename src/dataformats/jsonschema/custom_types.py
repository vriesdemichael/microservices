from typing import Any, Literal, Type

Number = int | float

# JsonType = Number | bool | None | str | dict[str, 'JsonType'] | list['JsonType']
SimpleTypeString = Literal["array", "boolean", "integer", "null", "number", "object", "string"]
python_types = Type[list | bool | int | None | dict[str, Any] | str | Number | dict | None]
json_to_python_type: dict[str, python_types] = {
    "array": list,
    "boolean": bool,
    "integer": int,
    "number": Number,  # type: ignore
    "object": dict,
    "string": str,
    "null": type(None),
}

unset_value = "unset"
Unset = Literal["unset"]
