import pytest
from dataformats.jsonschema.custom_types import JsonType
from dataformats.jsonschema.json_pointer import Pointer


def test_pointer_from_string():
    string_pointer = "/path/to/object"
    pointer = Pointer.from_string(string_pointer)
    assert pointer == Pointer("path", "to", "object")


def test_pointer_from_parts():
    assert Pointer("path", "to", "object")


def test_pointer_str():
    p = Pointer("path", "to", "object")
    assert str(p) == "/path/to/object"


def test_pointer_str_escaped():
    p = Pointer("path", "to", "slash/part")
    assert str(p) == "/path/to/slash~1part"


def test_pointer_escape():
    assert "~0~0~1~1~0~0" == Pointer._escape_part("~~//~~")


def test_pointer_unescape():
    assert "~~//~~" == Pointer._unescape_part("~0~0~1~1~0~0".replace("~1", "/"))


def test_url_encoded():
    assert str(Pointer.from_string("/some%20place%2Ffrom%23url")) == "/some place/from#url"


def test_follow_success():
    pointer = Pointer.from_string("/path/to/1/object")
    object: JsonType = {"path": {"to": ["nope", {"object": "target"}]}}
    assert pointer.follow_pointer(object) == "target"


def test_follow_fail_list_index():
    pointer = Pointer.from_string("/path/to/3/object")
    object: JsonType = {"path": {"to": ["nope", {"object": "target"}]}}

    with pytest.raises(ValueError) as e:
        pointer.follow_pointer(object)

    assert "/path/to/3 " in str(e.value)
    assert "out of bound" in str(e.value)


def test_follow_fail_key():
    pointer = Pointer.from_string("/path/to/1/object")
    object: JsonType = {"path": {"to": ["nope", {"wrong_key": "target"}]}}
    with pytest.raises(ValueError) as e:
        pointer.follow_pointer(object)

    assert "/path/to/1/object " in str(e.value)
    assert "'object' is not contained in the dict object with keys ['wrong_key']" in str(e.value)


def test_follow_fail_non_numeric_list_index():
    pointer = Pointer.from_string("/path/to/one/object")
    object: JsonType = {"path": {"to": ["nope", {"object": "target"}]}}

    with pytest.raises(ValueError) as e:
        pointer.follow_pointer(object)

    assert "/path/to/one " in str(e.value)
    assert "non numeric:" in str(e.value)


def test_iteration():
    pointer = Pointer.from_string("/some/pointer")
    parts = list(pointer)
    assert parts == pointer.parts


def test_repr():
    pointer = Pointer.from_string("/some/pointer")
    assert 'Pointer("some", "pointer")' == repr(pointer)


def test_pointer_beyond_lead():
    pointer = Pointer.from_string("/some/pointer")
    object: JsonType = {"some": "string"}
    with pytest.raises(ValueError) as exception_info:
        pointer.follow_pointer(object)
    assert (
        """Could not descend any further for pointer /some/pointer at /some/pointer with next part pointer because the current object is of type <class 'str'>"""
        in str(exception_info.value)
    )


def test_add_parts():
    pointer = Pointer.from_string("/some/pointer")
    pointer.add_part("added_part")
    object: JsonType = {"some": {"pointer": {"added_part": "pointer_target"}}}
    assert "pointer_target" == pointer.follow_pointer(object)


def test_extended_copy():
    pointer = Pointer.from_string("/some/pointer")
    extended_pointer = pointer.extended_copy("child")
    assert pointer != extended_pointer
    assert str(extended_pointer) == "/some/pointer/child"


def test_is_parent_of_true():
    parent = Pointer.from_string("/some/pointer")
    child = Pointer.from_string("/some/pointer/child")
    assert parent.is_parent_of(child)


def test_is_parent_of_false():
    parent = Pointer.from_string("/some/pointer")
    child = Pointer.from_string("/some/pointer/child")
    assert not child.is_parent_of(parent)


def test_is_parent_of_self():
    somepointer = Pointer.from_string("/some/pointer")
    assert not somepointer.is_parent_of(somepointer)


def test_is_child_of_true():
    parent = Pointer.from_string("/some/pointer")
    child = Pointer.from_string("/some/pointer/child")
    assert child.is_child_of(parent)


def test_is_child_of_false():
    parent = Pointer.from_string("/some/pointer")
    child = Pointer.from_string("/some/pointer/child")
    assert not parent.is_child_of(child)


def test_is_child_of_self():
    somepointer = Pointer.from_string("/some/pointer")
    assert not somepointer.is_child_of(somepointer)


def test_parent_child_not_matching():
    random_pointer = Pointer.from_string("/random/123")
    somepointer = Pointer.from_string("/some/pointer")

    assert not random_pointer.is_child_of(somepointer)
    assert not random_pointer.is_parent_of(somepointer)


@pytest.mark.parametrize(
    ["pointer_string", "expected_length"],
    [("", 0), ("/some/pointer", 2), ("/some/pointer//", 4)],
    ids=["empty", "normal_pointer", "empty parts"],
)
def test_len(pointer_string: str, expected_length: int):
    print(Pointer.from_string(pointer_string).parts)
    assert len(Pointer.from_string(pointer_string)) == expected_length

def test_parent():
    somepointer = Pointer.from_string("/some/pointer")
    assert somepointer.parent == Pointer.from_string("/some")

def test_parent_empty():
    emptypointer = Pointer()
    with pytest.raises(ValueError):
        _ = emptypointer.parent
