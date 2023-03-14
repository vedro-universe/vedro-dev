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
        if path.name == "__init__.py":
            path = path.parent

        try:
            rel_path = path.relative_to(Path.cwd())
        except ValueError:
            return None
        else:
            return ".".join(rel_path.with_suffix("").parts)
