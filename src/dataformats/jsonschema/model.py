import logging
import re
from pathlib import Path
from typing import Any, Generator, Self, Tuple, TypeVar

import requests
from dataformats.jsonschema.custom_types import SimpleTypeString, Unset, unset_value
from dataformats.jsonschema.dereference import dereference
from pydantic import (
    BaseModel,
    Extra,
    Field,
    PrivateAttr,
    conlist,
    root_validator,
    validator,
)

TSchema = TypeVar("TSchema", bound="Draft4MetaSchema")

logger = logging.getLogger(__name__)


# TODO: additionalItems default value allows keywords other than the ones in here, how to deal with those?


class Draft4MetaSchema(BaseModel):
    class Config:
        allow_population_by_field_name = True
        extra = Extra.allow
        # frozen = True

    id: str | Unset = unset_value
    schema_: str | Unset = Field(default=unset_value, alias="$schema")
    title: str | Unset = unset_value
    description: str | Unset = unset_value
    default: Any | Unset = unset_value
    multipleOf: float | Unset = Field(default=unset_value, gt=0)  # cast to float for proper validation
    maximum: float | Unset = unset_value  # cast to float for proper validation
    exclusiveMaximum: bool | Unset = unset_value
    minimum: float | Unset = unset_value  # cast to float for proper validation
    exclusiveMinimum: bool | Unset = unset_value
    maxLength: int | Unset = unset_value
    minLength: int | Unset = unset_value
    pattern: str | Unset = unset_value
    additionalItems: bool | TSchema | Unset = unset_value  # type: ignore
    items: conlist(TSchema, min_items=1) | TSchema | Unset = unset_value  # type: ignore
    maxItems: int | Unset = unset_value
    minItems: int | Unset = unset_value
    uniqueItems: bool | Unset = unset_value
    maxProperties: int | Unset = unset_value
    minProperties: int | Unset = unset_value
    required: list[str] | Unset = unset_value
    additionalProperties: bool | TSchema | Unset = unset_value  # type: ignore
    definitions: dict[str, TSchema] | Unset = unset_value  # type: ignore
    properties: dict[str, TSchema] | Unset = unset_value  # type: ignore
    patternProperties: dict[str, TSchema] | Unset = unset_value  # type: ignore
    dependencies: dict[str, TSchema | list[str]] | Unset = unset_value  # type: ignore
    enum: Tuple[Any, ...] | Unset = unset_value
    type: SimpleTypeString | list[SimpleTypeString] | Unset = unset_value
    format: str | Unset = unset_value
    allOf: conlist(TSchema, min_items=1) | Unset = unset_value  # type: ignore
    anyOf: conlist(TSchema, min_items=1) | Unset = unset_value  # type: ignore
    oneOf: conlist(TSchema, min_items=1) | Unset = unset_value  # type: ignore
    not_: TSchema | Unset = Field(default=unset_value, alias="not")  # type: ignore
    ref_: str | Unset = Field(default=unset_value, alias="$ref")

    _parent_reference: TSchema | None = PrivateAttr(default=None)  # type: ignore
    _parent_json_pointer_to_here: str | None = PrivateAttr(default=None)
    _base_uri: str | None = PrivateAttr(default=None)

    def __init__(self, *args, **data):
        super().__init__(**data)
        if self.id != unset_value:
            self._base_uri = self.id
        for schema, pointer in self.direct_child_schemas:
            schema._parent_reference = self
            schema._parent_json_pointer_to_here = pointer
        # self.resolve_references()
        # self.deal_with_extras()

    @root_validator(pre=True)
    def resolve_references(cls, values: dict[str, Any]):
        logger.debug(f"Before resolve {values=}")
        dereference(values)
        logger.debug(f"After resolve {values=}")

        return values

    # def deal_with_extras(self):
    #     for extra_field in self.extra_fields:
    #         extra_value = getattr(self, extra_field)
    #         extra_pointer = f"{self.json_pointer}/{extra_field}"

    #         if isinstance(extra_value, dict):
    #             new_value = self.deal_with_extra_dict(extra_value, extra_pointer)
    #         elif isinstance(extra_value, list):
    #             new_value = self.deal_with_extra_list(extra_value, pointer=extra_pointer)
    #         else:
    #             new_value = extra_value
    #         setattr(self, extra_field, new_value)

    # def deal_with_extra_dict(self, dict_value: dict[str, Any], pointer: str):
    #     subschema = Draft4MetaSchema.parse_obj(dict_value)
    #     subschema._parent_reference = self
    #     subschema._parent_json_pointer_to_here = pointer
    #     return subschema

    # def deal_with_extra_list(self, list_value: list, pointer: str):
    #     new_list = []
    #     for idx, item in enumerate(list_value):
    #         item_pointer = f"{pointer}/{idx}"
    #         if isinstance(item, dict):
    #             schema = self.deal_with_extra_dict(item, item_pointer)
    #             new_list.append(schema)
    #         elif isinstance(item, list):
    #             new_list.append(self.deal_with_extra_list(item, item_pointer))
    #         else:
    #             new_list.append(item)
    #     return new_list

    @property
    def direct_child_schemas(self) -> Generator[Tuple[Self, str], None, None]:
        direct_schemas = ["additionalItems", "items", "additionalProperties", "not_"]
        list_schemas = ["items", "allOf", "anyOf", "oneOf"]
        dict_schemas = ["definitions", "properties", "patternProperties", "dependencies"]

        for schema_attr_name in direct_schemas:
            schema = getattr(self, schema_attr_name)
            json_pointer = schema_attr_name
            if isinstance(schema, type(self)):
                yield schema, json_pointer

        for schema_list_attr in list_schemas:
            schema_list = getattr(self, schema_list_attr)

            if isinstance(schema_list, list):
                for idx, schema in enumerate(schema_list):
                    json_pointer = f"{schema_list_attr}/{idx}"
                    if isinstance(schema, type(self)):
                        yield schema, json_pointer

        for schema_dict_attr in dict_schemas:
            schema_dict = getattr(self, schema_dict_attr)
            if isinstance(schema_dict, dict):
                for schema_key, schema in schema_dict.items():
                    json_pointer = f"{schema_dict_attr}/{schema_key}"
                    if isinstance(schema, type(self)):
                        yield schema, schema_key

    @property
    def base_uri(self) -> tuple[str, Self] | tuple[None, None]:
        """The base uri and the parent schema on which it is based"""
        current = self
        if current.id != unset_value:
            return current.id, self

        if not current._parent_reference:
            return None, None

        while current._parent_reference:
            current = current._parent_reference
            if current.id != unset_value:
                return current.id, current

        return None, None

    @property
    def top_level_schema(self) -> Self:
        current = self
        while current._parent_reference and (current := current._parent_reference):
            pass
        return current

    @property
    def json_pointer(self):
        pointer = ""
        if not self._parent_reference:
            return pointer

        current = self
        while current._parent_reference:
            if not current._parent_json_pointer_to_here:
                raise RuntimeError("No pointer but does have a parent")

            pointer = f"{pointer}/{current._parent_json_pointer_to_here}"
            current = current._parent_reference
        return pointer

    # def derefence(self, download_external=False):
    #     """
    #     Resolve the $ref keyword of this schema.


    #     Does inline dereference first, then canonical

    #     Inline dereferencing means: when an URI only contains a fragment
    #     (e.g. `#foo/bar/someplace` or `#definitions/foo` or `#someIdKeywordAnywhereInTheDoc`)
    #     The references will be searched for within the same document.

    #     Canonical derefencing looks for external sources. Examples:
    #     `https://docs.renovatebot.com/renovate-schema.json`,
    #     `relative-sibling.json#definitions/foo`,
    #     `some-obscure-reference` (where it is not an id within the document)
    #     The references will be downloaded or loaded from the filesystem.

    #     Since this is draft4 derefencing it will disregard any sibling keywords (which is stupid, since it is valid to have sibling keywords.. ahwell, stupid spec is stupid)
    #     """
    #     logger.debug(f"Dereferencing '{self.json_pointer}'")
    #     if self.ref_ == unset_value:
    #         raise ValueError("No $ref keyword in the schema to dereference")
    #     if self.ref_ == "":
    #         raise ValueError("empty schema reference found")
    #     if self.ref_.count("#") > 1:
    #         raise ValueError("Reference contains more than 1 #")

    #     if (
    #         self.ref_ == "http://json-schema.org/draft-04/schema#"
    #         or self.ref_ == "http://json-schema.org/draft-04/schema"
    #     ):
    #         # Separate to ensure it works without downloading
    #         target_schema = Draft4MetaSchema.parse_obj(DRAFT4_SCHEMA)
    #         # replace all non private keywords
    #         for key, value in target_schema.__dict__.items():
    #             setattr(self, key, value)
    #         return

    #     # add trailing # for consistent parsing
    #     ref = self.ref_ if "#" in self.ref_ else f"{self.ref_}#"
    #     external_part, fragment = ref.split("#")
    #     base_uri, base_uri_parent = self.base_uri

    #     # A ref can be:
    #     # 1. An absolute canonical URI, external part starts with a protocol
    #     # 2. An inline reference, which can be matched to an id keyword in the current scope
    #     #    The scope limited to first parent with an id keyword
    #     # 3. A relative canonical URI, which can be completed based on the base_uri of the current scope
    #     # 4. Just a fragment with a json pointer
    #     logger.debug(f"\t{external_part=} {fragment=}")
    #     if external_part:
    #         # 1. ref is an absolute canonical URI
    #         if ref.startswith("http://") or ref.startswith("https://"):
    #             if download_external:
    #                 target_schema = Draft4MetaSchema.from_external_url(external_part)
    #             else:
    #                 target_schema = Draft4MetaSchema()  # Empty schema, all items will be valid against it.
    #         else:
    #             if not base_uri_parent:
    #                 raise ValueError(
    #                     f"Could not resolve the relative ref '{ref}' because no base_uri is known for schema at '{self.json_pointer}'"
    #                 )
    #             # 2. check for inline references
    #             if id_schema := base_uri_parent.all_ids.get(external_part, None):
    #                 target_schema = id_schema
    #             # 3. complete the relative uri with the base_uri
    #             else:
    #                 # 3a. base_uri is a local path
    #                 if base_uri and base_uri.startswith("file://"):
    #                     target_path = Path(base_uri.replace("file://", "")).parent / external_part
    #                     if not target_path.exists():
    #                         raise ValueError(f"Referenced local file does not exist: {target_path}")
    #                     target_schema = Draft4MetaSchema.from_local_path(target_path)
    #                 # 3b. base_uri is a http/https uri
    #                 elif base_uri and (base_uri.startswith(("http://", "https://"))):
    #                     # complete the canonical uri
    #                     target_uri = "/".join(base_uri.split("/")[:-1]) + "/" + external_part
    #                     target_schema = Draft4MetaSchema.from_external_url(target_uri)
    #                 else:
    #                     raise ValueError(f"Could not determine the base uri for ref {ref}")
    #     else:
    #         # fragment only, resolve as json pointer from the first parent with an id keyword or top level
    #         if base_uri_parent:
    #             target_schema = base_uri_parent
    #         else:
    #             target_schema = self

    #     if fragment:
    #         # resolve fragment part (which contains a json pointer)
    #         target_schema = target_schema.resolve_pointer(fragment, download_external=download_external)

    #     # replace all non private keywords
    #     for key, value in target_schema.__dict__.items():
    #         setattr(self, key, value)
    #         self.deal_with_extras()
    #     logger.debug(f"Dereferenced {self.json_pointer}")

    # def resolve_pointer(self, pointer, download_external: bool = False) -> Self:
    #     logger.debug(f"Resolving pointer '{pointer}' at {self.json_pointer}")
    #     remap_to_alias = {
    #         "$ref": "ref_",
    #         "not": "not_",
    #         "$schema": "schema_",
    #     }
    #     escaped_parts = [remap_to_alias[x] if x in remap_to_alias else x for x in pointer.split("/") if x]
    #     unescaped_parts = [urllib.parse.unquote(x).replace("~1", "/").replace("~0", "~") for x in escaped_parts]

    #     current_part = unescaped_parts[0]
    #     future_parts = unescaped_parts[1:]
    #     if not current_part:
    #         raise RuntimeError(f"{pointer=} {current_part=} {future_parts=}")

    #     try:
    #         child_attr = getattr(self, current_part)
    #         if isinstance(child_attr, list):
    #             child_schema = child_attr[int(future_parts[0])]
    #             remaining_pointer = "/".join(escaped_parts[2:])
    #         elif isinstance(child_attr, dict):
    #             try:
    #                 child_schema = child_attr[future_parts[0]]
    #                 remaining_pointer = "/".join(escaped_parts[2:])
    #             except AttributeError as attribute_e:
    #                 try:
    #                     child_schema = self.__class__.parse_obj(child_attr)
    #                     remaining_pointer = "/".join(escaped_parts[1:])
    #                 except Exception as e:
    #                     logger.debug(type(e))
    #                     raise RuntimeError("TODO Set the correct exception type") from attribute_e

    #         else:
    #             child_schema = child_attr
    #             remaining_pointer = "/".join(escaped_parts[1:])
    #     except Exception as e:
    #         raise ValueError(
    #             f"Exception of type {type(e)} encountered while trying to resolve '{self.json_pointer}/{pointer} {self=}'"
    #         ) from e

    #     if not isinstance(child_schema, type(self)):
    #         raise ValueError(
    #             f"Cannot resolve pointer for item of type {type(child_schema)}, expected a schema instance "
    #             f"{self=} {pointer=} {child_schema=}"
    #         )

    #     if child_schema.ref_ is not unset_value:
    #         child_schema.derefence(download_external)

    #     if not remaining_pointer:
    #         return child_schema
    #     return child_schema.resolve_pointer(remaining_pointer, download_external)

    @property
    def all_ids(self) -> dict[str, Self]:
        ids: dict[str, Self] = dict()
        if self.id != unset_value:
            ids[self.id] = self
        for schema, _ in self.direct_child_schemas:
            ids.update(schema.all_ids)
        return ids

    @classmethod
    def from_external_url(cls, url: str):
        response = requests.get(url)
        response.raise_for_status()
        instance = cls.parse_obj(response.json())
        if instance.id == unset_value:
            instance.id = url
        instance._base_uri = url
        return instance

    @classmethod
    def from_local_path(cls, local_path: str | Path):
        instance = cls.parse_file(local_path)
        if instance.id != unset_value and instance.id.startswith(("http://", "https://", "file://")):
            instance._base_uri = instance.id
        else:
            instance.id = f"file://{str(Path(local_path).absolute())}"
            instance._base_uri = instance.id
        return instance

    @validator("id", "ref_")
    def uri_checks(cls, uri_value: str):
        if uri_value == "":
            raise ValueError("uri may not be empty string")
        if uri_value.startswith("https://") or uri_value.startswith("http://"):
            #     # TODO validate URL is not malformed
            pass
        # TODO normalize uri with hyperlink or whatever
        return uri_value

    @validator("id")
    def non_empty(cls, id_value):
        if id_value == "#":
            raise ValueError("id may not be an empty fragment")
        return id_value

    @validator("schema_")
    def schema_valid(cls, schema_value: str):
        # TODO make canonical normalized uri
        # TODO what changes when this is not a standard draft4 schema? Just definitions?
        schema_value_with_pound = f"{schema_value.strip()}#" if "#" not in schema_value else schema_value
        latest_string = "http://json-schema.org/schema#"
        draft_4_string = "http://json-schema.org/draft-04/schema#"
        if schema_value_with_pound == draft_4_string:
            pass
        if schema_value_with_pound == latest_string or schema_value == draft_4_string:
            pass
        return schema_value

    @validator("exclusiveMaximum")
    def exclusive_maximum_must_also_have_maximum(cls, value, values):
        if values["maximum"] == unset_value:
            raise ValueError("exclusiveMaximum is dependant on the presence of 'maximum', which is not set")
        return value

    @validator("exclusiveMinimum")
    def exclusive_minimum_must_also_have_minimum(cls, value, values):
        if values["minimum"] == unset_value:
            raise ValueError("exclusiveMinimum is dependant on the presence of 'maximum', which is not set")
        return value

    @validator("patternProperties")
    def check_pattern_properties_regex(cls, value: dict[str, Any]):
        for regex_key in value.keys():
            try:
                re.compile(regex_key)  # throws if invalid
            except Exception as e:
                logger.debug(e)
                logger.debug(regex_key)
                raise
        return value

    @validator("pattern")
    def check_pattern_regex(cls, value: str):
        try:
            re.compile(value)  # throws if invalid
        except re.error as e:
            raise ValueError from e

        return value

    def dict(self, *args, **kwargs):
        kwargs["exclude_defaults"] = True
        kwargs["exclude_unset"] = True
        kwargs["by_alias"] = True
        d = super().dict(*args, **kwargs)
        return d

    def __repr__(self):
        return str(dict(self.dict()))

    def __str__(self):
        return f"<Draft4Schema: {str(dict(self.dict()))}>"

    @property
    def extra_fields(self) -> set[str]:
        return set(self.__dict__) - set(self.__fields__)
