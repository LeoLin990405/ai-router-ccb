"""
AST Analyzer for CCB

Provides code structure analysis using tree-sitter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import sys

# Try to import tree-sitter
try:
    import tree_sitter
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


@dataclass
class ASTNode:
    """A node in the AST."""
    type: str
    text: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    children: List["ASTNode"] = field(default_factory=list)


@dataclass
class FunctionInfo:
    """Information about a function."""
    name: str
    file: str
    start_line: int
    end_line: int
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    is_method: bool = False
    class_name: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    file: str
    start_line: int
    end_line: int
    bases: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ImportInfo:
    """Information about an import."""
    module: str
    names: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from: bool = False
    line: int = 0


def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


HANDLED_EXCEPTIONS = (Exception,)



try:
    from .ast_analyzer_classes import ASTAnalyzerClassMixin
    from .ast_analyzer_parse import ASTAnalyzerParseMixin
except ImportError:  # pragma: no cover - script mode
    from ast_analyzer_classes import ASTAnalyzerClassMixin
    from ast_analyzer_parse import ASTAnalyzerParseMixin


class ASTAnalyzer(ASTAnalyzerParseMixin, ASTAnalyzerClassMixin):
    """AST analyzer using tree-sitter."""

    LANGUAGE_MAP: Dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
    }


def get_ast_analyzer() -> ASTAnalyzer:
    """Get the global AST analyzer instance."""
    global _ast_analyzer
    if _ast_analyzer is None:
        _ast_analyzer = ASTAnalyzer()
    return _ast_analyzer
