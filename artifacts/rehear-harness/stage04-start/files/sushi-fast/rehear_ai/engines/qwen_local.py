"""Local weights only. The optional ML runtime is imported at first real loading."""
import importlib.metadata
from pathlib import Path

from .base import AssessmentEngineError, ResearchEngine


class LocalRuntimeUnavailable(AssessmentEngineError):
    pass


class QwenLocalEngine(ResearchEngine):
    def __init__(self, config, *, loader=None):
        if config.engine != "qwen_local":
            raise ValueError("QwenLocalEngine requires explicit qwen_local configuration")
        super().__init__(config)
        self._injected = loader is not None
        self._loader = loader or load_transformers_runtime
        self._runtime = None

    @property
    def identity(self):
        return super().identity.model_copy(update={
            "runtime_binding": "injected_loader" if self._injected else "transformers_local"})

    def _prepare(self):
        if self._runtime is None:
            self._runtime = self._loader(self.config)
            if not callable(getattr(self._runtime, "generate", None)):
                self._runtime = None
                raise AssessmentEngineError("local loader must return a generate(messages) runtime")

    def _infer(self, messages):
        return self._runtime.generate(messages)


def load_transformers_runtime(config):
    for package, expected in config.runtime_versions.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise LocalRuntimeUnavailable(f"missing local dependency: {package}; use a separately pinned model environment") from exc
        if actual != expected:
            raise LocalRuntimeUnavailable(f"runtime version mismatch for {package}; align the explicit runtime_versions lock")
    for location in (config.model, config.tokenizer, config.adapter):
        if location is not None and not Path(location).is_dir():
            raise LocalRuntimeUnavailable("local model/tokenizer/adapter directory missing; automatic downloads are disabled")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise LocalRuntimeUnavailable("local torch/transformers runtime is unavailable") from exc
    tokenizer = AutoTokenizer.from_pretrained(config.tokenizer, revision=config.tokenizer_revision,
        local_files_only=True, trust_remote_code=False)
    if not tokenizer.chat_template:
        raise LocalRuntimeUnavailable("a verified model-specific chat template is required")
    model = AutoModelForCausalLM.from_pretrained(config.model, revision=config.model_revision,
        local_files_only=True, trust_remote_code=False)
    if model.config.model_type != config.model_family:
        raise LocalRuntimeUnavailable("loaded model family does not match the explicitly selected family")
    if config.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, config.adapter, revision=config.adapter_revision,
            local_files_only=True, is_trainable=False)
    model.to(device=config.device, dtype=getattr(torch, config.dtype))
    model.eval()

    class Runtime:
        def generate(self, messages):
            template_options = {"enable_thinking": False} if config.model_family == "qwen3" else {}
            inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                return_tensors="pt", return_dict=True, **template_options).to(config.device)
            if inputs["input_ids"].shape[-1] > config.max_input_tokens:
                raise AssessmentEngineError("input exceeds token budget; supply an explicitly scoped evidence export")
            options = {"max_new_tokens": config.max_new_tokens, "do_sample": config.temperature > 0,
                       "max_time": config.timeout_s}
            if config.temperature > 0:
                options["temperature"] = config.temperature
            with torch.inference_mode():
                generated = model.generate(**inputs, **options)
            return tokenizer.decode(generated[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)

    return Runtime()
