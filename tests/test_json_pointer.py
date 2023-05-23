import pytest
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
    object = {"path": {"to": ['nope', {"object": "target"}]}}
    assert pointer.follow_pointer(object) == "target"

def test_follow_fail_list_index():
    pointer = Pointer.from_string("/path/to/3/object")
    object = {"path": {"to": ['nope', {"object": "target"}]}}

    with pytest.raises(ValueError) as e:
        pointer.follow_pointer(object)

    assert "/path/to/3 " in str(e.value)
    assert "out of bound" in str(e.value)


def test_follow_fail_key():
    pointer = Pointer.from_string("/path/to/1/object")
    object = {"path": {"to": ['nope', {"wrong_key": "target"}]}}
    with pytest.raises(ValueError) as e:
        pointer.follow_pointer(object)

    assert "/path/to/1/object " in str(e.value)
    assert "'object' is not contained in the dict object with keys ['wrong_key']" in str(e.value)

def test_follow_fail_non_numeric_list_index():
    pointer = Pointer.from_string("/path/to/one/object")
    object = {"path": {"to": ['nope', {"object": "target"}]}}

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
    data = {"some": "string"}
    with pytest.raises(ValueError) as exception_info:
        pointer.follow_pointer(data)
    assert """Could not descend any further for pointer /some/pointer at /some/pointer with next part pointer because the current object is of type <class 'str'>""" in str(exception_info.value)

def test_add_parts():
    pointer = Pointer.from_string("/some/pointer")
    pointer.add_part("added_part")
    data = {"some": {"pointer": {"added_part": "pointer_target"}}}
    assert "pointer_target" == pointer.follow_pointer(data)
