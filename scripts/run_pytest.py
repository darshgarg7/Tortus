"""Run pytest while avoiding a macOS libedit/readline crash in some Python builds."""

import builtins
import sys
from collections.abc import Mapping, Sequence
from types import ModuleType
from typing import Any, cast


def main() -> int:
    """Run main."""
    original_import: Any = builtins.__import__

    def guarded_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ) -> ModuleType:
        """Return guarded import."""
        if name == "readline":
            raise ImportError("readline disabled for pytest startup")
        return cast(ModuleType, original_import(name, globals, locals, fromlist, level))

    builtins.__import__ = guarded_import
    import pytest

    return int(pytest.main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
