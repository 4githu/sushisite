from .config import EngineConfig


def create_engine(config: EngineConfig | None = None):
    config = config or EngineConfig()
    if config.engine == "fake":
        from .engines.fake import FakeEngine
        return FakeEngine(config)
    from .engines.qwen_local import QwenLocalEngine
    return QwenLocalEngine(config)
