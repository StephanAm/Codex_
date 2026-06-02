class DummyBackend:
    """Returns the prompt that would have been sent to the LLM instead of calling one."""

    @property
    def model_name(self) -> str:
        return "dummy"

    def generate(self, system: str, user: str) -> str:
        divider = "─" * 60
        return (
            f"[SYSTEM]\n{divider}\n{system.strip()}\n\n"
            f"[USER]\n{divider}\n{user.strip()}\n"
        )
