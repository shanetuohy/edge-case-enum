"""Unit tests for the AST-based edge-case scanner."""

from edge_case_enum.scanner import scan_source


def _categories(result):
    return [f.category for f in result.findings]


# -- division --

def test_division_variable_divisor():
    result = scan_source("x = a / b\n")
    assert "division" in _categories(result)


def test_division_constant_nonzero_ok():
    result = scan_source("x = a / 2\n")
    assert "division" not in _categories(result)


def test_division_constant_zero_flagged():
    result = scan_source("x = a / 0\n")
    assert "division" in _categories(result)


def test_floor_division_flagged():
    result = scan_source("x = a // b\n")
    assert "division" in _categories(result)


def test_modulo_flagged():
    result = scan_source("x = a % b\n")
    assert "division" in _categories(result)


# -- optional params --

def test_optional_param_no_guard():
    code = """\
def foo(x=None):
    return x.upper()
"""
    result = scan_source(code)
    assert "optional-param" in _categories(result)


def test_optional_param_with_guard():
    code = """\
def foo(x=None):
    if x is None:
        return ""
    return x.upper()
"""
    result = scan_source(code)
    assert "optional-param" not in _categories(result)


def test_optional_param_truthiness_guard():
    code = """\
def foo(x=None):
    if x:
        return x.upper()
    return ""
"""
    result = scan_source(code)
    assert "optional-param" not in _categories(result)


def test_kwonly_optional_param():
    code = """\
def foo(*, callback=None):
    callback()
"""
    result = scan_source(code)
    assert "optional-param" in _categories(result)


# -- bare indexing --

def test_bare_integer_index():
    result = scan_source("x = items[0]\n")
    assert "bare-index" in _categories(result)


def test_bare_variable_index():
    result = scan_source("x = items[i]\n")
    assert "bare-index" in _categories(result)


# -- bare except --

def test_bare_except():
    code = """\
try:
    risky()
except:
    pass
"""
    result = scan_source(code)
    assert "bare-except" in _categories(result)


def test_specific_except_ok():
    code = """\
try:
    risky()
except ValueError:
    pass
"""
    result = scan_source(code)
    assert "bare-except" not in _categories(result)


# -- file I/O --

def test_open_without_with():
    code = "f = open('data.txt')\n"
    result = scan_source(code)
    assert "file-io" in _categories(result)


def test_open_with_with_ok():
    code = """\
with open('data.txt') as f:
    data = f.read()
"""
    result = scan_source(code)
    assert "file-io" not in _categories(result)


# -- unchecked .get() --

def test_get_without_default():
    code = "v = d.get('key')\n"
    result = scan_source(code)
    assert "unchecked-get" in _categories(result)


def test_get_with_default_ok():
    code = "v = d.get('key', 0)\n"
    result = scan_source(code)
    assert "unchecked-get" not in _categories(result)


# -- string format --

def test_format_on_variable():
    code = "result = template.format(name='Alice')\n"
    result = scan_source(code)
    assert "string-format" in _categories(result)


def test_format_on_literal_ok():
    code = "result = 'Hello {name}'.format(name='Alice')\n"
    result = scan_source(code)
    assert "string-format" not in _categories(result)


# -- parse error --

def test_syntax_error():
    result = scan_source("def ???\n")
    assert "parse-error" in _categories(result)


# -- clean code --

def test_clean_code_no_findings():
    code = """\
def add(a: int, b: int) -> int:
    return a + b
"""
    result = scan_source(code)
    assert len(result.findings) == 0
