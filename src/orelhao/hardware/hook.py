class HookSensor:
    """Interface inicial do gancho. Na v0.0 o estado é simulado."""

    def __init__(self) -> None:
        self._off_hook = False

    def set_off_hook(self, value: bool) -> None:
        self._off_hook = value

    def is_off_hook(self) -> bool:
        return self._off_hook
