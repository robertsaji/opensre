"""Base tool interface for opensre integrations.

All tools must inherit from BaseTool and implement the required methods
as defined in .cursor/rules/tools.mdc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Encapsulates the result of a tool execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success


class BaseTool(ABC):
    """Abstract base class for all opensre tools.

    Concrete tools must implement `is_available`, `extract_params`, and `run`
    following the contract described in tools.mdc.

    Example::

        class MyTool(BaseTool):
            my_tool_name = "my_tool"

            def is_available(self) -> bool:
                return shutil.which("mytool") is not None

            def extract_params(self, context: dict[str, Any]) -> dict[str, Any]:
                return {"target": context["target"]}

            def run(self, params: dict[str, Any]) -> ToolResult:
                ...
    """

    #: Unique snake_case identifier for this tool (required by tools.mdc)
    my_tool_name: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "my_tool_name", ""):
            raise TypeError(
                f"{cls.__name__} must define a non-empty `my_tool_name` class attribute."
            )

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the underlying tool/binary/service is reachable."""

    @abstractmethod
    def extract_params(self, context: dict[str, Any]) -> dict[str, Any]:
        """Extract and validate tool-specific parameters from a graph node context.

        Args:
            context: The node execution context passed down from the graph runner.

        Returns:
            A dict of parameters that will be forwarded to :meth:`run`.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """

    @abstractmethod
    def run(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given parameters.

        Args:
            params: Validated parameters returned by :meth:`extract_params`.

        Returns:
            A :class:`ToolResult` describing the outcome.
        """

    def safe_run(self, context: dict[str, Any]) -> ToolResult:
        """Convenience wrapper: extract params then run, catching top-level errors."""
        if not self.is_available():
            return ToolResult(
                success=False,
                error=f"Tool '{self.my_tool_name}' is not available in this environment.",
            )
        try:
            params = self.extract_params(context)
            return self.run(params)
        except Exception as exc:  # noqa: BLE001
            # Include the exception type in the error message for easier debugging
            return ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
