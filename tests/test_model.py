


# def test_incomplete_model():
#     Draft4MetaSchema(maximum=1)


# def test_max_dependency():
#     with pytest.raises(expected_exception=ValidationError):
#         Draft4MetaSchema(exclusiveMaximum=True)


# def test_min_dependency():
#     with pytest.raises(expected_exception=ValidationError):
#         Draft4MetaSchema(exclusiveMinimum=True)


# def test_recursive():
#     Draft4MetaSchema(properties={"test_property": Draft4MetaSchema()})


# def test_from_json():
#     schema = Draft4MetaSchema.parse_raw('{"maximum": 3}')
#     assert schema.maximum == 3


# def test_from_json_recursive():
#     schema = Draft4MetaSchema.parse_raw('{"items": {"maximum": 3}}')
#     assert isinstance(schema.items, Draft4MetaSchema)
#     assert schema.items.maximum == 3


# def test_can_instantiate_alias_schema():
#     schema = Draft4MetaSchema(**{"$schema": "derp"})
#     assert schema.schema_ == "derp"


# def test_can_instantiate_non_alias_schema_():
#     schema = Draft4MetaSchema(schema_="derp")  # type: ignore
#     assert schema.schema_ == "derp"


# def test_can_load_own_schema():
#     schema = Draft4MetaSchema.parse_obj(DRAFT4_SCHEMA)


# def test_print_schema(draf_4_meta_self: Draft4MetaSchema, capsys: pytest.CaptureFixture[str]):
#     print(draf_4_meta_self)
#     captured_output = capsys.readouterr()
#     assert len(captured_output.out) > 0
#     assert len(captured_output.err) == 0


# def test_dict(draf_4_meta_self: Draft4MetaSchema):
#     dict_schema = draf_4_meta_self.dict(exclude_unset=True, by_alias=True)
#     assert "$schema" in dict_schema
#     assert "definitions" in dict_schema
#     assert len(dict_schema["definitions"]) > 0


# def test_json_schema(draft_4_empty):
#     Draft4MetaSchema.schema(by_alias=True)


# def test_parent_reference(draf_4_meta_self: Draft4MetaSchema):
#     properties_meta = draf_4_meta_self.properties
#     assert isinstance(properties_meta, dict)
#     for properties_meta_schema in properties_meta.values():
#         assert properties_meta_schema._parent_reference is not None
#         assert id(properties_meta_schema._parent_reference) == id(draf_4_meta_self)
