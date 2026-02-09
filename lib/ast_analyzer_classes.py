"""Auto-split mixins for ASTAnalyzer."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tree_sitter
except ImportError:  # pragma: no cover - optional dependency
    tree_sitter = None  # type: ignore[assignment]

try:
    from .ast_analyzer import (
        ASTNode,
        ClassInfo,
        FunctionInfo,
        HAS_TREE_SITTER,
        HANDLED_EXCEPTIONS,
        ImportInfo,
        _warn,
    )
except ImportError:  # pragma: no cover - script mode
    from ast_analyzer import (
        ASTNode,
        ClassInfo,
        FunctionInfo,
        HAS_TREE_SITTER,
        HANDLED_EXCEPTIONS,
        ImportInfo,
        _warn,
    )


class ASTAnalyzerClassMixin:
    """Mixin methods extracted from ASTAnalyzer."""

    def find_classes(self, file_path: str) -> List[ClassInfo]:
        """
        Find all classes in a file.

        Args:
            file_path: Path to the file

        Returns:
            List of ClassInfo
        """
        language = self._get_language_from_file(file_path)
        if not language:
            return self._find_classes_fallback(file_path)

        parser = self._get_parser(language)
        if not parser:
            return self._find_classes_fallback(file_path)

        try:
            content = Path(file_path).read_bytes()
            tree = parser.parse(content)

            classes = []
            self._extract_classes(tree.root_node, content, file_path, classes, language)
            return classes

        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to analyze {file_path}: {e}")
            return self._find_classes_fallback(file_path)

    def _extract_classes(
        self,
        node: Any,
        source: bytes,
        file_path: str,
        classes: List[ClassInfo],
        language: str,
    ) -> None:
        """Extract classes from AST nodes."""
        if language == "python" and node.type == "class_definition":
            cls = self._parse_python_class(node, source, file_path)
            if cls:
                classes.append(cls)

        elif language in ("javascript", "typescript", "tsx") and node.type == "class_declaration":
            cls = self._parse_js_class(node, source, file_path)
            if cls:
                classes.append(cls)

        for child in node.children:
            self._extract_classes(child, source, file_path, classes, language)

    def _parse_python_class(
        self,
        node: Any,
        source: bytes,
        file_path: str,
    ) -> Optional[ClassInfo]:
        """Parse a Python class definition."""
        name = None
        bases = []
        methods = []
        docstring = None

        for child in node.children:
            if child.type == "identifier":
                name = source[child.start_byte:child.end_byte].decode()
            elif child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(source[arg.start_byte:arg.end_byte].decode())
            elif child.type == "block":
                for stmt in child.children:
                    if stmt.type == "function_definition":
                        for c in stmt.children:
                            if c.type == "identifier":
                                methods.append(source[c.start_byte:c.end_byte].decode())
                                break
                    elif stmt.type == "expression_statement" and not docstring:
                        for expr in stmt.children:
                            if expr.type == "string":
                                docstring = source[expr.start_byte:expr.end_byte].decode()
                                break

        if not name:
            return None

        return ClassInfo(
            name=name,
            file=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            bases=bases,
            methods=methods,
            docstring=docstring,
        )

    def _parse_js_class(
        self,
        node: Any,
        source: bytes,
        file_path: str,
    ) -> Optional[ClassInfo]:
        """Parse a JavaScript/TypeScript class."""
        name = None
        bases = []
        methods = []

        for child in node.children:
            if child.type == "identifier":
                name = source[child.start_byte:child.end_byte].decode()
            elif child.type == "class_heritage":
                for c in child.children:
                    if c.type == "identifier":
                        bases.append(source[c.start_byte:c.end_byte].decode())
            elif child.type == "class_body":
                for member in child.children:
                    if member.type == "method_definition":
                        for c in member.children:
                            if c.type == "property_identifier":
                                methods.append(source[c.start_byte:c.end_byte].decode())
                                break

        if not name:
            return None

        return ClassInfo(
            name=name,
            file=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            bases=bases,
            methods=methods,
        )

    def _find_classes_fallback(self, file_path: str) -> List[ClassInfo]:
        """Fallback class finder using regex."""
        import re

        classes = []
        try:
            content = Path(file_path).read_text()
            lines = content.split("\n")

            # Python pattern
            py_pattern = re.compile(r"^\s*class\s+(\w+)")
            # JS/TS pattern
            js_pattern = re.compile(r"^\s*class\s+(\w+)")

            for i, line in enumerate(lines):
                match = py_pattern.match(line) or js_pattern.match(line)
                if match:
                    name = match.group(1)
                    classes.append(ClassInfo(
                        name=name,
                        file=file_path,
                        start_line=i + 1,
                        end_line=i + 1,
                    ))

        except HANDLED_EXCEPTIONS:
            pass

        return classes

    def get_imports(self, file_path: str) -> List[ImportInfo]:
        """
        Get all imports in a file.

        Args:
            file_path: Path to the file

        Returns:
            List of ImportInfo
        """
        imports = []
        try:
            content = Path(file_path).read_text()
            lines = content.split("\n")

            import re

            # Python imports
            py_import = re.compile(r"^\s*import\s+(\S+)(?:\s+as\s+(\w+))?")
            py_from = re.compile(r"^\s*from\s+(\S+)\s+import\s+(.+)")

            # JS/TS imports
            js_import = re.compile(r"^\s*import\s+(?:{([^}]+)}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]")

            for i, line in enumerate(lines):
                # Python import
                match = py_import.match(line)
                if match:
                    imports.append(ImportInfo(
                        module=match.group(1),
                        alias=match.group(2),
                        line=i + 1,
                    ))
                    continue

                # Python from import
                match = py_from.match(line)
                if match:
                    module = match.group(1)
                    names = [n.strip() for n in match.group(2).split(",")]
                    imports.append(ImportInfo(
                        module=module,
                        names=names,
                        is_from=True,
                        line=i + 1,
                    ))
                    continue

                # JS/TS import
                match = js_import.match(line)
                if match:
                    names = []
                    if match.group(1):
                        names = [n.strip() for n in match.group(1).split(",")]
                    elif match.group(2):
                        names = [match.group(2)]
                    imports.append(ImportInfo(
                        module=match.group(3),
                        names=names,
                        is_from=True,
                        line=i + 1,
                    ))

        except HANDLED_EXCEPTIONS:
            pass

        return imports


# Singleton instance
_ast_analyzer: Optional[ASTAnalyzer] = None


