"""Keep legacy facade monkeypatches attached to canonical module symbols."""

from __future__ import annotations

from types import ModuleType


def install(
    facade: ModuleType,
    modules: tuple[ModuleType, ...],
    names: set[str] | None = None,
) -> None:
    del names
    targets: dict[str, tuple[ModuleType, ...]] = {}
    for module in modules:
        for name in vars(module):
            if name.startswith("__"):
                continue
            owners = list(targets.get(name, ()))
            if module not in owners:
                owners.append(module)
            targets[name] = tuple(owners)

    canonical = {}
    for name, owners in targets.items():
        exported = [owner for owner in owners if name in getattr(owner, "__all__", ())]
        canonical[name] = exported[0] if exported else owners[-1]

    class CompatibilityModule(ModuleType):
        def __getattribute__(self, name: str) -> object:
            owner = canonical.get(name)
            if owner is not None:
                return getattr(owner, name)
            return super().__getattribute__(name)

        def __setattr__(self, name: str, value: object) -> None:
            owners = targets.get(name, ())
            if not owners:
                super().__setattr__(name, value)
                return
            for module in owners:
                setattr(module, name, value)

    facade.__class__ = CompatibilityModule
