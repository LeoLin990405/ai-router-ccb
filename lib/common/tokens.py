"""Token estimation helpers."""

from __future__ import annotations

import re
from typing import Dict

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]")


def estimate_tokens(text: str) -> int:
    """Estimate token count using a lightweight language-aware heuristic."""
    if not text:
        return 0
    cjk_count = len(_CJK_PATTERN.findall(text))
    ascii_count = len(text) - cjk_count
    return int(cjk_count / 1.5 + ascii_count / 4)


def estimate_input_output_tokens(input_text: str, output_text: str) -> Dict[str, int]:
    """Estimate input/output/total token counts."""
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
