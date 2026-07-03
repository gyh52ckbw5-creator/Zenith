"""Kucuk, guvenli yerel araclar. Zenith, LLM'e gitmeden once kullanicinin
mesajinin bu araclardan birine uydugunu kontrol eder (guvenilir sekilde her
saglayicida calisan bir 'function calling' katmani olmadigi icin basit ve
ongorulebilir bir komut eslesmesi tercih edildi)."""

from __future__ import annotations

import ast
import operator
import re
from datetime import datetime

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Desteklenmeyen ifade")


def calculate(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    result = _safe_eval(tree.body)
    return str(result)


CALC_PATTERN = re.compile(r"^\s*(?:hesapla|calc)\s*[:=]?\s*(.+)$", re.IGNORECASE)
TIME_PATTERN = re.compile(r"^\s*(?:saat kac|tarih ne|what time|now)\s*\??\s*$", re.IGNORECASE)


def try_handle_locally(user_input: str) -> str | None:
    """Mesaj yerel bir arac ile cevaplanabiliyorsa cevabi dondurur, yoksa None."""
    calc_match = CALC_PATTERN.match(user_input)
    if calc_match:
        try:
            return f"Sonuc: {calculate(calc_match.group(1))}"
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
            return "Bu ifadeyi hesaplayamadim, lutfen basit bir matematik ifadesi yaz (orn: hesapla: 12*7)."

    if TIME_PATTERN.match(user_input):
        return f"Su an: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return None
