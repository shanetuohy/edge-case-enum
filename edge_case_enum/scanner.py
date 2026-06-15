"""AST-based scanner that detects code patterns likely to have unhandled edge cases."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    file: str
    line: int
    category: str
    message: str


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)

    def add(self, file: str, line: int, category: str, message: str) -> None:
        self.findings.append(Finding(file=file, line=line, category=category, message=message))


def _annotate_parents(tree: ast.AST) -> None:
    """Set a _parent attribute on every node in the tree."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node  # type: ignore[attr-defined]


class EdgeCaseVisitor(ast.NodeVisitor):
    """Walks an AST and collects edge-case-prone patterns."""

    def __init__(self, filename: str, result: ScanResult) -> None:
        self.filename = filename
        self.result = result
        self._func_stack: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    # -- helpers --

    def _add(self, node: ast.AST, category: str, message: str) -> None:
        self.result.add(self.filename, node.lineno, category, message)

    def _is_guarded_by_zero_check(self, node: ast.AST) -> bool:
        """Heuristic: we don't do control-flow analysis, so we never consider
        division 'guarded'. Real guard detection would require CFG work."""
        return False

    # -- detectors --

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            # Skip constant divisors that are clearly non-zero
            if isinstance(node.right, ast.Constant) and node.right.value not in (0, 0.0):
                pass
            else:
                self._add(node, "division", "Division without zero-check on divisor")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_optional_params(node)
        self._func_stack.append(node)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _check_optional_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Flag parameters with default=None that are used in the body without
        an explicit None guard (if x is None / if x is not None / if x)."""
        none_params: set[str] = set()
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, ast.Constant) and default.value is None:
                # Map default back to the parameter name
                idx_defaults = len(node.args.defaults)
                idx_kw = len(node.args.kw_defaults)
                # We'll collect all None-defaulted param names below
                pass

        # Collect param names with None defaults
        positional = node.args.args
        pos_defaults = node.args.defaults
        offset = len(positional) - len(pos_defaults)
        for i, d in enumerate(pos_defaults):
            if isinstance(d, ast.Constant) and d.value is None:
                none_params.add(positional[offset + i].arg)

        for i, d in enumerate(node.args.kw_defaults):
            if d is not None and isinstance(d, ast.Constant) and d.value is None:
                none_params.add(node.args.kwonlyargs[i].arg)

        if not none_params:
            return

        # Check for guards: if <param> is None / if <param> is not None / if <param>
        guarded: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                test = child.test
                names = _extract_guard_names(test)
                guarded.update(names)

        for param in none_params - guarded:
            self._add(node, "optional-param", f"Parameter '{param}' defaults to None but has no None-guard in body")

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Flag bare indexing (not slicing) on names — potential IndexError / KeyError
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
            # Constant integer index — could be out of range
            self._add(node, "bare-index", f"Bare index [{node.slice.value}] without bounds check")
        elif isinstance(node.slice, ast.Name):
            self._add(node, "bare-index", f"Bare index [{node.slice.id}] without bounds check")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self._add(node, "bare-except", "Bare except catches all exceptions including SystemExit and KeyboardInterrupt")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # open() without a context manager
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if not self._inside_with(node):
                self._add(node, "file-io", "open() called outside a with-statement — resource may leak")

        # .get() result used without None check — only flag direct attribute access on .get()
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            # Only flag if there's exactly 1 arg (no default supplied)
            if len(node.args) == 1 and not node.keywords:
                self._add(node, "unchecked-get", ".get() called without a default — result may be None")

        self.generic_visit(node)

    def _inside_with(self, node: ast.AST) -> bool:
        """Check if a node is a context_expr of a with-statement by walking parents."""
        parent = getattr(node, "_parent", None)
        while parent is not None:
            if isinstance(parent, ast.withitem):
                return True
            if isinstance(parent, (ast.With, ast.AsyncWith)):
                # Check if node is one of the context_exprs
                for item in parent.items:
                    if item.context_expr is node:
                        return True
            parent = getattr(parent, "_parent", None)
        return False

    def visit_For(self, node: ast.For) -> None:
        # Iterating over a variable that could be empty with no guard
        # We only flag for-else without an else body, where the iterable is a name
        # (indicating it might be empty). This is a light heuristic.
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # String formatting with .format() on non-literal strings
        if node.attr == "format" and not isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            # The base is not a string literal — could fail at runtime
            self._add(node, "string-format", ".format() called on a non-literal string — may raise KeyError/IndexError")
        self.generic_visit(node)


def _extract_guard_names(test: ast.AST) -> set[str]:
    """Extract variable names that are being guarded in an if-test."""
    names: set[str] = set()
    if isinstance(test, ast.Compare):
        # if x is None / if x is not None
        if isinstance(test.left, ast.Name):
            names.add(test.left.id)
        for comp in test.comparators:
            if isinstance(comp, ast.Name):
                names.add(comp.id)
    elif isinstance(test, ast.Name):
        # if x:
        names.add(test.id)
    elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        if isinstance(test.operand, ast.Name):
            names.add(test.operand.id)
    elif isinstance(test, ast.BoolOp):
        for value in test.values:
            names.update(_extract_guard_names(value))
    return names


def scan_source(source: str, filename: str = "<string>") -> ScanResult:
    """Scan a Python source string and return findings."""
    result = ScanResult()
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        result.add(filename, 0, "parse-error", "Could not parse file")
        return result
    _annotate_parents(tree)
    visitor = EdgeCaseVisitor(filename, result)
    visitor.visit(tree)
    return result


def scan_file(path: Path) -> ScanResult:
    """Scan a single Python file."""
    source = path.read_text(encoding="utf-8", errors="replace")
    return scan_source(source, filename=str(path))


def scan_directory(path: Path) -> ScanResult:
    """Recursively scan all .py files in a directory."""
    combined = ScanResult()
    for py_file in sorted(path.rglob("*.py")):
        file_result = scan_file(py_file)
        combined.findings.extend(file_result.findings)
    return combined
