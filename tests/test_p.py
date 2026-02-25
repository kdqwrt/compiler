import pytest
from src.preprocessor.preprocessor import Preprocessor
from src.preprocessor.macros import MacroProcessor


def test_remove_single_line_comment():
    source = 'int x = 5; // это комментарий'
    pp = Preprocessor(source)
    result = pp.process()
    assert '//' not in result
    assert pp.get_errors() == []

def test_remove_multiline_comment():
    source = '''
    /* многострочный
       комментарий */
    int x = 5;
    '''
    pp = Preprocessor(source)
    result = pp.process()
    assert '/*' not in result
    assert '*/' not in result
    assert pp.get_errors() == []

def test_keep_comment_in_string():
    source = 'string s = "не // удалять";'
    pp = Preprocessor(source)
    result = pp.process()
    assert 'не // удалять' in result
    assert pp.get_errors() == []

def test_unterminated_block_comment():
    source = 'int x = 5; /* незакрытый комментарий'
    pp = Preprocessor(source)
    result = pp.process()
    errors = pp.get_errors()
    assert any('Незавершенный блочный комментарий' in e for e in errors)


def test_macro_substitution():
    source = '''
    #define MAX 100
    #define HELLO "Hello"
    int value = MAX;
    string msg = HELLO;
    '''
    mp = MacroProcessor()
    result = mp.process_directives(source)
    assert 'MAX' not in result
    assert '100' in result
    assert 'HELLO' not in result
    assert '"Hello"' in result
    assert mp.get_errors() == []


def test_macro_recursion_protection():
    source = '''
    #define A B
    #define B A
    int x = A;
    '''
    mp = MacroProcessor()
    result = mp.process_directives(source)
    errors = mp.get_errors()
    # Проверка на рекурсию
    assert any('рекурси' in e.lower() for e in errors)


def test_ifdef_block():
    source = '''
    #define DEBUG
    #ifdef DEBUG
    int x = 1;
    #endif
    int y = 2;
    '''
    mp = MacroProcessor()
    result = mp.process_directives(source)
    assert 'int x = 1;' in result
    assert 'int y = 2;' in result

def test_ifndef_block():
    source = '''
    #ifndef RELEASE
    int x = 1;
    #endif
    int y = 2;
    '''
    mp = MacroProcessor()
    result = mp.process_directives(source)
    assert 'int x = 1;' in result
    assert 'int y = 2;' in result

def test_skipped_ifdef_block():
    source = '''
    #ifdef RELEASE
    int x = 1;
    #endif
    int y = 2;
    '''
    mp = MacroProcessor()
    result = mp.process_directives(source)
    # int x = 1; не должен попасть в результат
    assert 'int x = 1;' not in result
    assert 'int y = 2;' in result
