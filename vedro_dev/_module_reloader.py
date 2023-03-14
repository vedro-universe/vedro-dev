import importlib
import sys
from pathlib import Path
from typing import Set, Union

__all__ = ("ModuleReloader",)


class ModuleReloader:
    async def reload(self, ignore_modules: Set[str]) -> None:
        for name in list(sys.modules.keys()):
            if name in ignore_modules:
                continue
            module = sys.modules[name]
            module_path = getattr(module, "__file__", None)
            if module_path and self._path_to_module(Path(module_path)) == name:
                importlib.reload(module)

    def _path_to_module(self, path: Path) -> Union[str, None]:
        cwd = Path.cwd()

        if not path.is_relative_to(cwd):
            return None

        if path.name == "__init__.py":
            path = path.parent
        rel_path = path.relative_to(cwd)
        return ".".join(rel_path.with_suffix("").parts)
