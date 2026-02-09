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


class ASTAnalyzerParseMixin:
    """Mixin methods extracted from ASTAnalyzer."""

    def __init__(self):
        """Initialize the AST analyzer."""
        self._parsers: Dict[str, Any] = {}
        self._languages: Dict[str, Any] = {}

        if not HAS_TREE_SITTER:
            _warn("Warning: tree-sitter not installed. AST analysis will be limited.")

    def _get_parser(self, language: str) -> Optional[Any]:
        """Get or create a parser for a language."""
        if not HAS_TREE_SITTER:
            return None

        if language in self._parsers:
            return self._parsers[language]

        try:
            # Try to load the language
            lang_module = __import__(f"tree_sitter_{language}")
            lang = lang_module.language()

            parser = tree_sitter.Parser(lang)
            self._parsers[language] = parser
            self._languages[language] = lang

            return parser

        except ImportError:
            _warn(f"Warning: tree-sitter-{language} not installed")
            return None
        except HANDLED_EXCEPTIONS as e:
            _warn(f"Warning: Failed to load tree-sitter for {language}: {e}")
            return None

    def _get_language_from_file(self, file_path: str) -> Optional[str]:
        """Get the language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext)

    def parse_file(self, file_path: str) -> Optional[ASTNode]:
        """
        Parse a file into an AST.

        Args:
            file_path: Path to the file

        Returns:
            Root ASTNode or None if parsing failed
        """
        language = self._get_language_from_file(file_path)
        if not language:
            return None

        parser = self._get_parser(language)
        if not parser:
            return None

        try:
            content = Path(file_path).read_bytes()
            tree = parser.parse(content)
            return self._convert_node(tree.root_node, content)
        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to parse {file_path}: {e}")
            return None

    def _convert_node(self, node: Any, source: bytes) -> ASTNode:
        """Convert a tree-sitter node to ASTNode."""
        children = [self._convert_node(child, source) for child in node.children]

        return ASTNode(
            type=node.type,
            text=source[node.start_byte:node.end_byte].decode(errors="replace"),
            start_line=node.start_point[0] + 1,
            start_column=node.start_point[1] + 1,
            end_line=node.end_point[0] + 1,
            end_column=node.end_point[1] + 1,
            children=children,
        )

    def find_functions(self, file_path: str) -> List[FunctionInfo]:
        """
        Find all functions in a file.

        Args:
            file_path: Path to the file

        Returns:
            List of FunctionInfo
        """
        language = self._get_language_from_file(file_path)
        if not language:
            return self._find_functions_fallback(file_path)

        parser = self._get_parser(language)
        if not parser:
            return self._find_functions_fallback(file_path)

        try:
            content = Path(file_path).read_bytes()
            tree = parser.parse(content)

            functions = []
            self._extract_functions(tree.root_node, content, file_path, functions, language)
            return functions

        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to analyze {file_path}: {e}")
            return self._find_functions_fallback(file_path)

    def _extract_functions(
        self,
        node: Any,
        source: bytes,
        file_path: str,
        functions: List[FunctionInfo],
        language: str,
        class_name: Optional[str] = None,
    ) -> None:
        """Extract functions from AST nodes."""
        # Python function definitions
        if language == "python":
            if node.type == "function_definition":
                func = self._parse_python_function(node, source, file_path, class_name)
                if func:
                    functions.append(func)

            elif node.type == "class_definition":
                # Get class name
                for child in node.children:
                    if child.type == "identifier":
                        class_name = source[child.start_byte:child.end_byte].decode()
                        break

        # JavaScript/TypeScript function definitions
        elif language in ("javascript", "typescript", "tsx"):
            if node.type in ("function_declaration", "method_definition", "arrow_function"):
                func = self._parse_js_function(node, source, file_path, class_name)
                if func:
                    functions.append(func)

            elif node.type == "class_declaration":
                for child in node.children:
                    if child.type == "identifier":
                        class_name = source[child.start_byte:child.end_byte].decode()
                        break

        # Recurse into children
        for child in node.children:
            self._extract_functions(child, source, file_path, functions, language, class_name)

    def _parse_python_function(
        self,
        node: Any,
        source: bytes,
        file_path: str,
        class_name: Optional[str],
    ) -> Optional[FunctionInfo]:
        """Parse a Python function definition."""
        name = None
        parameters = []
        is_async = False
        docstring = None

        for child in node.children:
            if child.type == "identifier":
                name = source[child.start_byte:child.end_byte].decode()
            elif child.type == "parameters":
                for param in child.children:
                    if param.type == "identifier":
                        parameters.append(source[param.start_byte:param.end_byte].decode())
                    elif param.type in ("typed_parameter", "default_parameter"):
                        for p in param.children:
                            if p.type == "identifier":
                                parameters.append(source[p.start_byte:p.end_byte].decode())
                                break
            elif child.type == "block":
                # Check for docstring
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "string":
                                docstring = source[expr.start_byte:expr.end_byte].decode()
                                break
                        break

        # Check for async
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    text = source[child.start_byte:child.end_byte].decode()
                    if "async" in text.lower():
                        is_async = True

        if not name:
            return None

        return FunctionInfo(
            name=name,
            file=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            parameters=parameters,
            docstring=docstring,
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
        )

    def _parse_js_function(
        self,
        node: Any,
        source: bytes,
        file_path: str,
        class_name: Optional[str],
    ) -> Optional[FunctionInfo]:
        """Parse a JavaScript/TypeScript function."""
        name = None
        parameters = []
        is_async = False

        for child in node.children:
            if child.type == "identifier":
                name = source[child.start_byte:child.end_byte].decode()
            elif child.type == "property_identifier":
                name = source[child.start_byte:child.end_byte].decode()
            elif child.type == "formal_parameters":
                for param in child.children:
                    if param.type == "identifier":
                        parameters.append(source[param.start_byte:param.end_byte].decode())
                    elif param.type == "required_parameter":
                        for p in param.children:
                            if p.type == "identifier":
                                parameters.append(source[p.start_byte:p.end_byte].decode())
                                break

        # Check for async keyword
        text = source[node.start_byte:node.end_byte].decode()
        if text.startswith("async"):
            is_async = True

        if not name:
            return None

        return FunctionInfo(
            name=name,
            file=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            parameters=parameters,
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
        )

    def _find_functions_fallback(self, file_path: str) -> List[FunctionInfo]:
        """Fallback function finder using regex."""
        import re

        functions = []
        try:
            content = Path(file_path).read_text()
            lines = content.split("\n")

            # Python pattern
            py_pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)\s*\(")
            # JS/TS pattern
            js_pattern = re.compile(r"^\s*(async\s+)?function\s+(\w+)\s*\(|^\s*(\w+)\s*[=:]\s*(async\s+)?\(")

            for i, line in enumerate(lines):
                # Python
                match = py_pattern.match(line)
                if match:
                    is_async = match.group(1) is not None
                    name = match.group(2)
                    functions.append(FunctionInfo(
                        name=name,
                        file=file_path,
                        start_line=i + 1,
                        end_line=i + 1,
                        is_async=is_async,
                    ))
                    continue

                # JavaScript
                match = js_pattern.match(line)
                if match:
                    is_async = match.group(1) is not None or match.group(4) is not None
                    name = match.group(2) or match.group(3)
                    if name:
                        functions.append(FunctionInfo(
                            name=name,
                            file=file_path,
                            start_line=i + 1,
                            end_line=i + 1,
                            is_async=is_async,
                        ))

        except HANDLED_EXCEPTIONS:
            pass

        return functions

