from src.semantic.type_system import (
    INT_TYPE,
    FLOAT_TYPE,
    BOOL_TYPE,
    VOID_TYPE,
    STRING_TYPE,
    ERROR_TYPE,
    make_struct_type,
    make_function_type,
)


def test_builtin_type_equality():
    assert INT_TYPE.equals(INT_TYPE)
    assert FLOAT_TYPE.equals(FLOAT_TYPE)
    assert not INT_TYPE.equals(FLOAT_TYPE)


def test_assignable_same_type():
    assert INT_TYPE.is_assignable_from(INT_TYPE)
    assert FLOAT_TYPE.is_assignable_from(FLOAT_TYPE)
    assert BOOL_TYPE.is_assignable_from(BOOL_TYPE)
    assert STRING_TYPE.is_assignable_from(STRING_TYPE)


def test_int_assignable_to_float():
    assert FLOAT_TYPE.is_assignable_from(INT_TYPE)


def test_float_not_assignable_to_int():
    assert not INT_TYPE.is_assignable_from(FLOAT_TYPE)


def test_error_type_is_compatible_with_anything():
    assert INT_TYPE.is_assignable_from(ERROR_TYPE)
    assert ERROR_TYPE.is_assignable_from(INT_TYPE)


def test_struct_types_equal_by_name():
    p1 = make_struct_type("Point")
    p2 = make_struct_type("Point")
    q = make_struct_type("User")

    assert p1.equals(p2)
    assert not p1.equals(q)


def test_function_types_compare_signature():
    f1 = make_function_type([INT_TYPE, FLOAT_TYPE], BOOL_TYPE)
    f2 = make_function_type([INT_TYPE, FLOAT_TYPE], BOOL_TYPE)
    f3 = make_function_type([INT_TYPE], BOOL_TYPE)

    assert f1.equals(f2)
    assert not f1.equals(f3)