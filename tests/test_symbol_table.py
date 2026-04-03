from src.semantic.symbol_table import SymbolTable, SymbolInfo, SymbolKind, ScopeKind


def test_insert_and_lookup_global():
    table = SymbolTable()
    symbol = SymbolInfo(name="x", kind=SymbolKind.VARIABLE, line=1, column=1)

    assert table.insert("x", symbol) is True
    assert table.lookup("x") is symbol
    assert table.lookup_local("x") is symbol


def test_duplicate_insert_same_scope_fails():
    table = SymbolTable()
    s1 = SymbolInfo(name="x", kind=SymbolKind.VARIABLE, line=1, column=1)
    s2 = SymbolInfo(name="x", kind=SymbolKind.VARIABLE, line=2, column=1)

    assert table.insert("x", s1) is True
    assert table.insert("x", s2) is False


def test_lookup_in_parent_scope():
    table = SymbolTable()
    global_symbol = SymbolInfo(name="x", kind=SymbolKind.VARIABLE, line=1, column=1)
    table.insert("x", global_symbol)

    table.enter_scope("foo", ScopeKind.FUNCTION)

    assert table.lookup("x") is global_symbol
    assert table.lookup_local("x") is None


def test_lookup_local_prefers_current_scope():
    table = SymbolTable()
    global_symbol = SymbolInfo(name="x", kind=SymbolKind.VARIABLE, line=1, column=1)
    local_symbol = SymbolInfo(name="x", kind=SymbolKind.VARIABLE, line=2, column=1)

    table.insert("x", global_symbol)
    table.enter_scope("foo", ScopeKind.FUNCTION)
    assert table.insert("x", local_symbol) is True

    assert table.lookup("x") is local_symbol
    assert table.lookup_local("x") is local_symbol


def test_exit_scope_restores_parent():
    table = SymbolTable()
    table.enter_scope("foo", ScopeKind.FUNCTION)
    assert table.current_scope.name == "foo"

    table.exit_scope()
    assert table.current_scope.name == "global"