from typing import Literal

from pydantic import Field, model_validator

from .contracts import Contract, Text


class EngineConfig(Contract):
    engine: Literal["fake", "qwen_local"] = "fake"
    model: Text = "fake-abstain"
    model_revision: Text = "builtin-v1"
    tokenizer: Text = "none"
    tokenizer_revision: Text = "builtin-v1"
    adapter: Text | None = None
    adapter_revision: Text | None = None
    model_family: Literal["qwen2", "qwen3"] = "qwen3"
    runtime_versions: dict[str, Text] = Field(default_factory=dict)
    prompt_version: Text = "research16-json-v1"
    cache_enabled: bool = False
    temperature: float = Field(default=0, ge=0, le=2)
    max_new_tokens: int = Field(default=4096, strict=True, ge=1, le=32768)
    max_input_tokens: int = Field(default=16384, strict=True, ge=1)
    timeout_s: float = Field(default=120, gt=0)
    retries: int = Field(default=0, strict=True, ge=0, le=2)
    device: Literal["cpu", "cuda", "mps"] = "cpu"
    dtype: Literal["float32", "float16", "bfloat16"] = "float32"

    @model_validator(mode="after")
    def explicit_local_identity(self):
        if (self.adapter is None) != (self.adapter_revision is None):
            raise ValueError("adapter and adapter_revision must be supplied together")
        if self.engine == "qwen_local":
            if self.model in {"fake-abstain", "none"} or self.tokenizer == "none":
                raise ValueError("local model and tokenizer directories must be explicit")
            if self.model_revision == "builtin-v1" or self.tokenizer_revision == "builtin-v1":
                raise ValueError("local base/tokenizer revisions must be explicit")
            required = {"torch", "transformers"} | ({"peft"} if self.adapter else set())
            if not required <= self.runtime_versions.keys():
                raise ValueError("pin installed torch/transformers (and adapter peft) versions in runtime_versions")
        return self
