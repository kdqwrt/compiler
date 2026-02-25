from src.preprocessor.preprocessor import Preprocessor
from src.preprocessor.macros import MacroProcessor


def test_preprocessor():
    source = '''
    int x = 5; // это комментарий
    /* многострочный
       комментарий */
    string s = "не // удалять";
    '''

    pp = Preprocessor(source)
    result = pp.process()
    print("=== Препроцессор ===")
    print(result)
    print("Ошибки:", pp.get_errors())
    print()


def test_macros():
    source = '''\
#define MAX 100
#define HELLO "Hello"
int value = MAX;
string msg = HELLO;
'''
    mp = MacroProcessor()
    result = mp.process_directives(source)
    print("=== Макросы ===")
    print("Исходный код:")
    print(repr(source))
    print("\nРезультат:")
    print(result)
    print("Ошибки:", mp.get_errors())


if __name__ == "__main__":
    test_preprocessor()
    test_macros()