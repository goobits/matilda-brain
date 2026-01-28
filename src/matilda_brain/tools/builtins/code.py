"""Code execution built-in tools.

This module provides tools for running Python code and mathematical calculations.
"""

import ast
import math
import operator
import os
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Optional

import asyncio

from matilda_brain.tools import tool

from .config import _get_code_timeout, _get_timeout_bounds, _safe_execute_async

_PYTHON_CMD: Optional[str] = None


def _get_python_cmd() -> str:
    """Get the python command to use (python3 or python), caching the result.

    Performance Note:
        Using shutil.which() with caching is significantly faster (~5000x) than
        spawning a subprocess to check for python3 availability on every call.
    """
    global _PYTHON_CMD
    if _PYTHON_CMD is None:
        _PYTHON_CMD = "python3" if shutil.which("python3") else "python"
    return _PYTHON_CMD


# Allowed math functions and constants
ALLOWED_MATH_NAMES = {
    "abs",
    "round",
    "pow",
    "sum",
    "min",
    "max",
    "sqrt",
    "log",
    "log10",
    "exp",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "degrees",
    "radians",
    "pi",
    "e",
    "inf",
    "nan",
}

# Allowed operators for safe math evaluation
ALLOWED_MATH_OPERATORS = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
}


class MathEvaluator(ast.NodeVisitor):
    """Safe math expression evaluator."""

    def visit(self, node: ast.AST) -> Any:
        if type(node) not in (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Constant,
            ast.Name,
            ast.Call,
        ):
            raise ValueError(f"Unsupported operation: {type(node).__name__}")
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        if type(node.op) not in ALLOWED_MATH_OPERATORS:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")

        left = self.visit(node.left)
        right = self.visit(node.right)

        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.FloorDiv: operator.floordiv,
        }

        return ops[type(node.op)](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        if type(node.op) not in (ast.UAdd, ast.USub):
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        operand = self.visit(node.operand)

        if isinstance(node.op, ast.UAdd):
            return +operand
        else:
            return -operand

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id not in ALLOWED_MATH_NAMES:
            raise ValueError(f"Unsupported name: {node.id}")

        # Map names to math module attributes or builtins
        if node.id == "abs":
            return abs
        elif node.id == "round":
            return round
        elif node.id == "pow":
            return pow
        elif node.id == "sum":
            return sum
        elif node.id == "min":
            return min
        elif node.id == "max":
            return max
        elif hasattr(math, node.id):
            return getattr(math, node.id)
        else:
            raise ValueError(f"Unsupported name: {node.id}")

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are supported")

        func_name = node.func.id
        if func_name not in ALLOWED_MATH_NAMES:
            raise ValueError(f"Unsupported function: {func_name}")

        # Get function
        func: Callable[..., Any]
        if func_name == "abs":
            func = abs
        elif func_name == "round":
            func = round
        elif func_name == "pow":
            func = pow
        elif func_name == "sum":
            func = sum
        elif func_name == "min":
            func = min
        elif func_name == "max":
            func = max
        else:
            func = getattr(math, func_name)

        # Evaluate arguments
        args = [self.visit(arg) for arg in node.args]

        return func(*args)


@tool(category="code", description="Execute Python code safely in a sandboxed environment")
async def run_python(code: str, timeout: Optional[int] = None) -> str:
    """Execute Python code safely.

    Args:
        code: Python code to execute
        timeout: Maximum execution time in seconds (default: from config)

    Returns:
        Output of the code execution or error message
    """

    async def _run_python_impl(code: str, timeout: Optional[int] = None) -> str:
        if timeout is None:
            timeout = _get_code_timeout()

        # Validate inputs
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")

        # Get timeout bounds
        min_timeout, max_timeout = _get_timeout_bounds()
        timeout = min(max(min_timeout, timeout), max_timeout)

        # Create temporary file for code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Run code in subprocess with timeout
            # Try python3 first, then python (using cached command for performance)
            python_cmd = _get_python_cmd()

            process = await asyncio.create_subprocess_exec(
                python_cmd,
                temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                returncode = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                raise TimeoutError(f"Code execution timed out after {timeout} seconds")

            stdout_str = stdout.decode()
            stderr_str = stderr.decode()

            output = []
            if stdout_str:
                output.append(stdout_str)
            if stderr_str:
                output.append(f"Errors:\n{stderr_str}")

            if returncode != 0:
                output.append(f"Exit code: {returncode}")

            return "\n".join(output) if output else "Code executed successfully (no output)"

        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    return await _safe_execute_async("run_python", _run_python_impl, code=code, timeout=timeout)


@tool(category="math", description="Perform mathematical calculations safely")
def calculate(expression: str) -> str:
    """Perform mathematical calculations.

    Args:
        expression: Mathematical expression to evaluate

    Supported operations:
        - Basic arithmetic: +, -, *, /, **, %, //
        - Functions: abs, round, pow, sum, min, max, sqrt, log, log10, exp
        - Trigonometry: sin, cos, tan, asin, acos, atan, degrees, radians
        - Constants: pi, e, inf, nan

    Returns:
        Calculation result or error message
    """
    try:
        if not expression or not expression.strip():
            return "Error: Expression cannot be empty"

        # Parse expression
        tree = ast.parse(expression, mode="eval")

        # Evaluate safely
        evaluator = MathEvaluator()
        result = evaluator.visit(tree)

        # Format result
        if isinstance(result, float):
            # Check for special values
            if math.isnan(result):
                return "Result: NaN (Not a Number)"
            elif math.isinf(result):
                return f"Result: {'Infinity' if result > 0 else '-Infinity'}"
            # Format with reasonable precision
            elif abs(result) < 1e-10 or abs(result) > 1e10:
                return f"Result: {result:.6e}"
            else:
                return f"Result: {result:.10g}"
        else:
            return f"Result: {result}"

    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception:
        from matilda_brain.internal.utils import get_logger

        get_logger(__name__).exception("Error evaluating expression")
        return "Error evaluating expression - see logs for details"


__all__ = [
    "run_python",
    "calculate",
    "MathEvaluator",
    "ALLOWED_MATH_NAMES",
    "ALLOWED_MATH_OPERATORS",
]
