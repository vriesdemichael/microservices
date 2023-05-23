import urllib.parse
from typing import Any


class Pointer:
    def __init__(self, *parts: str):
        self.parts: list[str] = list(parts)

    @classmethod
    def from_string(cls, pointer_string):
        #pointers may be url encoded
        pointer_string = urllib.parse.unquote(pointer_string)
        parts = pointer_string.split("/")
        # the reference tokens can be escaped for `~` or `/` within a token
        parts = [cls._unescape_part(p) for p in parts if p]
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

    def follow_pointer(self, object: Any):
        """Descend into the given object following this json pointer

        Returns reference of the pointer within the object or raises a ValueError
        """
        current_location: Any = object

        for idx, pointer_part in enumerate(self.parts):
            processed_pointer = Pointer(*self.parts[:idx + 1])
            if isinstance(current_location, dict):
                try:
                    current_location = current_location[pointer_part]
                except KeyError as e:
                    raise ValueError(
                        f"Could not descend any further for pointer {self} at {processed_pointer}"
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

        return current_location

    def __str__(self):
        return "".join(f"/{self._escape_part(part)}" for part in self.parts)

    def __repr__(self):
        args = ', '.join(f'"{self._escape_part(part)}"' for part in self.parts)
        return f"Pointer({args})"

    def __eq__(self, other):
        return self.parts == other.parts
