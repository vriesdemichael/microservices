from typing import Any, Protocol


class Validator(Protocol):
    def validate(self, value: Any) -> None:
        ...

class VersionJsonSchema(Protocol):
    DRAFT_VERSION: str




# class DictItemsAsAttr:
#     __slots__ = ()
#     __getattr__ = dict.__getitem__
#     __setattr__ = dict.__setitem__  # type: ignore

