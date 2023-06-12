import urllib.parse
from logging import getLogger
from typing import Any, Self

from dataformats.jsonschema.custom_types import JsonType

logger = getLogger("json pointer resolver")

class Pointer:
    def __init__(self, *parts: str):
        self.parts: list[str] = list(parts)
        if not self.parts or self.parts[0] != "":
            self.parts = ["", *self.parts]

    @classmethod
    def from_string(cls, pointer_string):
        #pointers may be url encoded
        pointer_string = urllib.parse.unquote(pointer_string)
        # if pointer_string and pointer_string[0] == "/":
        #     pointer_string = pointer_string[1:]
        parts = pointer_string.split("/")
        # the reference tokens can be escaped for `~` or `/` within a token
        parts = [cls._unescape_part(p) for p in parts]
        return cls(*parts)

    @classmethod
    def _unescape_part(cls, part: str):
        # `~1` -> `/` and `~0` -> `~`
        part = part.replace("~1", "/")
        part = part.replace("~0", "~")
        return part

    @classmethod
    def _escape_part(cls, part: str):
        # `~0` -> `~` and `~1` -> `/`
        part = part.replace("~", "~0")
        part = part.replace("/", "~1")
        return part

    def __iter__(self):
        return self.parts.__iter__()

    def add_part(self, part: str):
        # This is the only place where parts are escaped
        part = self._unescape_part(part)
        self.parts.append(part)

    def extended_copy(self, part: str):
        """Convenience method to create a copy and add a part"""
        p = Pointer(*self.parts)
        p.add_part(part)
        return p

    def follow_pointer(self, object: JsonType) -> JsonType:
        """Descend into the given object following this json pointer

        Returns reference of the pointer within the object or raises a ValueError
        """
        current_location: Any = object
        logger.info(f"Resolving {self} in {object}")

        for idx, pointer_part in enumerate(self.parts):
            processed_pointer = Pointer(*self.parts[:idx + 1])
            try:
                if isinstance(current_location, dict):
                    try:
                        current_location = current_location[pointer_part]
                    except KeyError as e:
                        raise ValueError(
                            f"Could not descend any further for pointer {self} at {processed_pointer}. "
                            f"key '{pointer_part}' is not contained in the dict object with keys {list(current_location.keys())}"
                        ) from e
                elif isinstance(current_location, list):
                    if not pointer_part.isdigit():
                        raise ValueError(
                            f"Could not descend any further for pointer {self} at {processed_pointer}"
                            f" index of list is non numeric: {pointer_part}"
                        )
                    try:
                        current_location = current_location[int(pointer_part)]
                    except IndexError as e:
                        raise ValueError(
                            f"Could not descend any further for pointer {self} at {processed_pointer}"
                            f" the given index {pointer_part} is out of bound for the given "
                            f"list of len {len(current_location)}"
                        ) from e
                else:
                    raise ValueError(
                        f"Could not descend any further for pointer {self} at {processed_pointer}"
                        f" with next part {pointer_part} because the current object is of type {type(current_location)}"
                    )
            except ValueError:
                if pointer_part == "":
                    continue
                raise

        return current_location

    @property
    def parent(self) -> Self:
        if len(self) == 0:
            raise ValueError("root pointer has no parent")
        return self.__class__(*self.parts[:-1])

    def is_parent_of(self, other: Self):
        return self.parts == other.parts[:len(self) + 1] and len(self) != len(other)

    def is_child_of(self, other: Self):
        return self.parts[:len(other) + 1] == other.parts and len(self) != len(other)

    def __str__(self):
        return "".join(f"/{self._escape_part(part)}" for part in self.parts[1:])

    def __repr__(self):
        args = ', '.join(f'"{self._escape_part(part)}"' for part in self.parts[1:])
        return f"Pointer({args})"

    def __eq__(self, other):
        return self.parts == other.parts

    def __len__(self):
        return len(self.parts[1:])

    def __hash__(self):
        return hash(str(self))
