from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


class AgentToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}
        self._descriptions: dict[str, str] = {}
        self._schemas: dict[str, dict] = {}

    def register(self, tool: Any) -> None:
        name = getattr(tool, "name", None)
        description = getattr(tool, "description", None)
        schema = getattr(tool, "arguments_schema", None)
        execute = getattr(tool, "execute", None)

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "agent tool must have a non-empty name"
            )

        if name != name.strip():
            raise ValueError(
                "agent tool name cannot contain surrounding whitespace"
            )

        if name in self._tools:
            raise ValueError(
                f"agent tool already registered: {name}"
            )

        if not callable(execute):
            raise ValueError(
                f"agent tool '{name}' must implement execute()"
            )

        if (
            not isinstance(description, str)
            or not description.strip()
        ):
            raise ValueError(
                f"agent tool '{name}' must have a description"
            )

        if (
            not isinstance(schema, dict)
            or schema.get("type") != "object"
        ):
            raise ValueError(
                f"agent tool '{name}' must define an object "
                "argument schema"
            )

        if schema.get("additionalProperties") is not False:
            raise ValueError(
                f"agent tool '{name}' must reject additional arguments"
            )

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ValueError(
                f"agent tool '{name}' has an invalid argument schema"
            ) from exc

        self._tools[name] = tool
        self._descriptions[name] = description.strip()
        self._schemas[name] = deepcopy(schema)

    def get(self, name: str) -> Any:
        if name not in self._tools:
            raise ValueError(
                f"unknown agent tool: {name}"
            )

        return self._tools[name]

    def validate_arguments(
        self,
        name: str,
        arguments: dict,
    ) -> None:
        self.get(name)

        if not isinstance(arguments, dict):
            raise ValueError(
                f"invalid arguments for agent tool '{name}': "
                "arguments must be an object"
            )

        validator = Draft202012Validator(self._schemas[name])

        errors = sorted(
            validator.iter_errors(arguments),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )

        if errors:
            details = []

            for error in errors:
                path = (
                    "/".join(
                        str(part) for part in error.absolute_path
                    )
                    or "<root>"
                )
                details.append(f"{path}: {error.message}")

            raise ValueError(
                f"invalid arguments for agent tool '{name}': "
                + "; ".join(details)
            )

    def validate_context(
        self,
        name: str,
        context: Any,
        arguments: dict,
    ) -> None:
        """Run the registered tool's optional authorization guard."""
        tool = self.get(name)
        scope_validator = getattr(tool, "validate_context", None)

        if scope_validator is None:
            return

        if not callable(scope_validator):
            raise ValueError(
                f"agent tool '{name}' has an invalid context validator"
            )

        scope_validator(context, arguments)

    def execute(
        self,
        name: str,
        context: Any,
        **arguments: Any,
    ) -> Any:
        """Validate arguments and scope immediately before execution."""
        self.validate_arguments(name, arguments)
        self.validate_context(name, context, arguments)

        tool = self.get(name)
        return tool.execute(**arguments)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def describe_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": self._descriptions[name],
                "arguments_schema": deepcopy(self._schemas[name]),
            }
            for name in sorted(self._tools)
        ]