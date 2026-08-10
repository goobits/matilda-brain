"""Central safety and approval policy for tool execution."""

from __future__ import annotations

import ast
import ipaddress
import json
import re
import socket
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Union, cast

import bleach  # type: ignore[import-untyped]
import validators

from ..config.manager import get_config_value
from ..core.types import Proposal, RiskLevel

ConfigPath = Union[str, Path]


@dataclass
class ExecutionConfig:
    """Runtime limits and approval controls for tool execution."""

    max_retries: Optional[int] = None
    timeout_seconds: Optional[float] = None
    enable_fallbacks: bool = True
    enable_input_sanitization: bool = True
    log_level: str = "INFO"
    allowed_file_roots: Optional[List[ConfigPath]] = None
    allow_private_networks: Optional[bool] = None
    require_approval: Optional[bool] = None
    approval_threshold: Union[RiskLevel, str] = RiskLevel.HIGH

    def __post_init__(self) -> None:
        if self.max_retries is None:
            self.max_retries = int(get_config_value("tools.executor.max_retries", 3))
        if self.timeout_seconds is None:
            self.timeout_seconds = float(get_config_value("tools.executor.timeout_seconds", 30.0))
        if self.allowed_file_roots is None:
            configured_roots = get_config_value("tools.policy.file_roots", None)
            self.allowed_file_roots = configured_roots if isinstance(configured_roots, list) else []
        if self.allow_private_networks is None:
            self.allow_private_networks = bool(get_config_value("tools.policy.allow_private_networks", False))
        if self.require_approval is None:
            self.require_approval = bool(get_config_value("tools.policy.require_approval", False))
        if isinstance(self.approval_threshold, str):
            self.approval_threshold = RiskLevel(self.approval_threshold.lower())

    @property
    def file_roots(self) -> List[Path]:
        configured = [Path(root).expanduser().resolve() for root in self.allowed_file_roots or []]
        if configured:
            return configured
        defaults = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve(), Path("/var/tmp").resolve()]
        return list(dict.fromkeys(root for root in defaults if root.exists()))


class InputSanitizer:
    """Validate untrusted tool inputs without silently broadening authority."""

    DANGEROUS_PATTERNS: ClassVar[List[str]] = [
        r"^\s*sudo\s+",
        r"\brm\s+-rf\s+/",
        r"\bdel\s+/[sq]",
        r"\bformat\s+[c-z]:",
        r"\.\./",
        r"\.\.\\",
        r"/etc/passwd",
        r"/etc/shadow",
        r"C:\\Windows\\System32",
        r"^\x7fELF",
        r"^MZ",
    ]
    CODE_DANGEROUS_PATTERNS: ClassVar[List[str]] = [
        r"os\.(system|popen|exec\w*|spawn\w*)\s*\(",
        r"subprocess\.(run|call|Popen|check_output|check_call|getoutput|getstatusoutput)\s*\(",
        r"\b(eval|exec|compile|__import__)\s*\(",
        r"getattr\s*\(\s*(os|subprocess|__import__)",
        r"from\s+(subprocess|os)\s+import\s+",
        r"import\s+(subprocess|os)(\s+as\s+\w+)?",
        r"\b(open|globals|locals)\s*\(",
        r"__builtins__\s*\[",
    ]

    @classmethod
    def sanitize_string(
        cls,
        value: str,
        max_length: int = 10_000,
        allow_code: bool = True,
        *,
        strip_html: bool = True,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")
        if len(value) > max_length:
            raise ValueError(f"String too long: {len(value)} > {max_length}")
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE | re.MULTILINE):
                raise ValueError("Potentially dangerous content detected")
        if allow_code:
            for pattern in cls.CODE_DANGEROUS_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE | re.MULTILINE):
                    raise ValueError("Dangerous code pattern detected")

        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
        if not allow_code and strip_html:
            sanitized = str(bleach.clean(sanitized, strip=True))
        return sanitized.strip()

    @staticmethod
    def sanitize_path(path: str, allowed_roots: Optional[Sequence[ConfigPath]] = None) -> Path:
        if not isinstance(path, str):
            raise ValueError(f"Expected string path, got {type(path)}")
        if not path.strip():
            raise ValueError("Path cannot be empty")

        decoded_path = urllib.parse.unquote(path)
        if ".." in PurePath(path).parts or ".." in PurePath(decoded_path).parts:
            raise ValueError("Path traversal detected")

        resolved_path = Path(decoded_path).expanduser().resolve()
        roots = (
            [Path(root).expanduser().resolve() for root in allowed_roots]
            if allowed_roots
            else ExecutionConfig().file_roots
        )
        if not any(resolved_path.is_relative_to(root) for root in roots):
            raise ValueError(f"Path outside allowed roots: {resolved_path}")
        return resolved_path

    @staticmethod
    def sanitize_glob(pattern: str) -> str:
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("Glob pattern cannot be empty")
        decoded = urllib.parse.unquote(pattern)
        if Path(decoded).is_absolute() or ".." in PurePath(decoded).parts:
            raise ValueError("Glob pattern may not escape the selected directory")
        return decoded

    @classmethod
    def sanitize_url(cls, url: str, *, allow_private_networks: bool = False) -> str:
        if not isinstance(url, str):
            raise ValueError(f"Expected string URL, got {type(url)}")
        url = url.strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are allowed")
        if parsed.username or parsed.password:
            raise ValueError("Credentials in URLs are not allowed")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL hostname is required")
        if not allow_private_networks:
            cls._validate_hostname(hostname)
        if not validators.url(url):
            raise ValueError(f"Invalid URL format: {url}")
        return url

    @classmethod
    def validate_url_target(cls, url: str, *, allow_private_networks: bool = False) -> str:
        sanitized = cls.sanitize_url(url, allow_private_networks=allow_private_networks)
        if allow_private_networks:
            return sanitized

        parsed = urllib.parse.urlsplit(sanitized)
        assert parsed.hostname is not None
        addresses = cls._resolve_host(parsed.hostname, parsed.port)
        if not addresses:
            raise ValueError(f"Could not resolve URL hostname: {parsed.hostname}")
        for address in addresses:
            cls._validate_ip(address)
        return sanitized

    @classmethod
    def _validate_hostname(cls, hostname: str) -> None:
        normalized = hostname.rstrip(".").lower()
        if normalized == "localhost" or normalized.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Private or local network targets are not allowed")
        try:
            cls._validate_ip(ipaddress.ip_address(normalized))
        except ValueError as exc:
            if "not allowed" in str(exc):
                raise

    @staticmethod
    def _resolve_host(hostname: str, port: Optional[int]) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        try:
            return {ipaddress.ip_address(result[4][0]) for result in socket.getaddrinfo(hostname, port)}
        except socket.gaierror as exc:
            raise ValueError(f"Could not resolve URL hostname: {hostname}") from exc

    @staticmethod
    def _validate_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError(f"Private or unsafe network target is not allowed: {address}")

    @classmethod
    def sanitize_json(cls, json_str: str) -> Dict[str, Any]:
        if not isinstance(json_str, str):
            raise ValueError(f"Expected JSON string, got {type(json_str)}")
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

        def sanitize_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {key: sanitize_recursive(value) for key, value in obj.items()}
            if isinstance(obj, list):
                return [sanitize_recursive(item) for item in obj]
            if isinstance(obj, str):
                return cls.sanitize_string(obj, allow_code=False)
            return obj

        return cast(Dict[str, Any], sanitize_recursive(data))


class PythonPolicyValidator(ast.NodeVisitor):
    """Reject Python capabilities that escape the restricted subprocess."""

    SAFE_IMPORTS: ClassVar[set[str]] = {
        "collections",
        "datetime",
        "decimal",
        "fractions",
        "functools",
        "itertools",
        "json",
        "math",
        "operator",
        "random",
        "re",
        "statistics",
        "string",
        "time",
    }
    BLOCKED_NAMES: ClassVar[set[str]] = {
        "__import__",
        "breakpoint",
        "compile",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "open",
        "setattr",
        "delattr",
        "type",
        "vars",
    }

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._validate_import(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level or node.module is None:
            raise ValueError("Relative imports are not allowed")
        self._validate_import(node.module)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.BLOCKED_NAMES or node.id.startswith("__"):
            raise ValueError(f"Python name is not allowed: {node.id}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            raise ValueError(f"Private Python attributes are not allowed: {node.attr}")
        self.generic_visit(node)

    def _validate_import(self, module: str) -> None:
        root_module = module.split(".", 1)[0]
        if root_module not in self.SAFE_IMPORTS:
            raise ValueError(f"Python import is not allowed: {root_module}")


class ToolPolicy:
    """Apply sanitization, risk classification, and approval rules consistently."""

    RISK_ORDER: ClassVar[Dict[RiskLevel, int]] = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    TOOL_RISKS: ClassVar[Dict[str, RiskLevel]] = {
        "calculate": RiskLevel.LOW,
        "get_current_time": RiskLevel.LOW,
        "list_directory": RiskLevel.LOW,
        "read_file": RiskLevel.LOW,
        "web_search": RiskLevel.LOW,
        "http_request": RiskLevel.MEDIUM,
        "write_file": RiskLevel.HIGH,
        "run_python": RiskLevel.HIGH,
    }

    def __init__(self, config: Optional[ExecutionConfig] = None) -> None:
        self.config = config or ExecutionConfig()

    def sanitize_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        sanitized: Dict[str, Any] = {}
        for key, value in arguments.items():
            try:
                if key in {"file_path", "path"} and isinstance(value, str):
                    sanitized[key] = str(InputSanitizer.sanitize_path(value, self.config.file_roots))
                elif key == "pattern" and isinstance(value, str):
                    sanitized[key] = InputSanitizer.sanitize_glob(value)
                elif key == "url" and isinstance(value, str):
                    sanitized[key] = InputSanitizer.sanitize_url(
                        value,
                        allow_private_networks=bool(self.config.allow_private_networks),
                    )
                elif key == "code" and isinstance(value, str):
                    code = InputSanitizer.sanitize_string(value, allow_code=True)
                    self.validate_python(code)
                    sanitized[key] = code
                elif key == "expression" and isinstance(value, str):
                    sanitized[key] = InputSanitizer.sanitize_string(value, allow_code=True)
                elif key == "content" and isinstance(value, str):
                    max_size = int(get_config_value("tools.max_file_size", 10_485_760))
                    sanitized[key] = InputSanitizer.sanitize_string(
                        value,
                        max_length=max_size,
                        allow_code=False,
                        strip_html=False,
                    )
                elif key == "data" and isinstance(value, str):
                    sanitized[key] = value
                    if value.lstrip().startswith(("{", "[")):
                        InputSanitizer.sanitize_json(value)
                elif isinstance(value, str):
                    sanitized[key] = InputSanitizer.sanitize_string(value, allow_code=False)
                else:
                    sanitized[key] = value
            except ValueError as exc:
                raise ValueError(f"Invalid argument '{key}': {exc}") from exc
        return sanitized

    @staticmethod
    def validate_python(code: str) -> None:
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise ValueError(f"Invalid Python syntax: {exc.msg}") from exc
        PythonPolicyValidator().visit(tree)

    def risk_level(self, tool_name: str, arguments: Dict[str, Any]) -> RiskLevel:
        risk = self.TOOL_RISKS.get(tool_name, RiskLevel.MEDIUM)
        if tool_name == "http_request" and str(arguments.get("method", "GET")).upper() not in {"GET", "HEAD"}:
            return RiskLevel.HIGH
        return risk

    def proposal(self, tool_name: str, arguments: Dict[str, Any]) -> Proposal:
        risk = self.risk_level(tool_name, arguments)
        return Proposal(
            tool_name=tool_name,
            action_name="execute",
            params=self._redact_params(arguments),
            risk_level=risk,
            reasoning=f"{tool_name} requires explicit approval at {risk.value} risk.",
        )

    @classmethod
    def _redact_params(cls, value: Any, key: str = "") -> Any:
        if key and any(
            marker in key.lower() for marker in ("authorization", "cookie", "key", "password", "secret", "token")
        ):
            return "***"
        if isinstance(value, dict):
            return {item_key: cls._redact_params(item_value, item_key) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [cls._redact_params(item) for item in value]
        return value

    def approval_required(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        if not self.config.require_approval:
            return False
        threshold = cast(RiskLevel, self.config.approval_threshold)
        return self.RISK_ORDER[self.risk_level(tool_name, arguments)] >= self.RISK_ORDER[threshold]

    def authorize(self, tool_name: str, arguments: Dict[str, Any], *, approved: bool = False) -> Optional[Proposal]:
        if not approved and self.approval_required(tool_name, arguments):
            return self.proposal(tool_name, arguments)
        return None


__all__ = ["ExecutionConfig", "InputSanitizer", "ToolPolicy"]
