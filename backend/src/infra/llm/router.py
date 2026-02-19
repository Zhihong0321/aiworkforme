import logging
from typing import Dict, List, Optional, Any
from .schemas import LLMTask, LLMRequest, LLMResponse, LLMMessage
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(
        self, 
        providers: Dict[str, BaseLLMProvider], 
        routing_config: Dict[LLMTask, str],
        task_model_config: Optional[Dict[LLMTask, Optional[str]]] = None,
        default_provider: str = "zai"
    ):
        self.providers = providers
        self.routing_config = routing_config
        self.task_model_config = task_model_config or {}
        self.default_provider = default_provider

    async def execute(
        self, 
        task: LLMTask, 
        messages: List[Dict[str, str] | LLMMessage], 
        **kwargs
    ) -> LLMResponse:
        """
        Main entry point for executing an LLM task.
        Automatically routes to the correct provider based on task.
        """
        # 1. Normalize Messages
        normalized_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                normalized_messages.append(LLMMessage(**msg))
            else:
                normalized_messages.append(msg)

        # 2. Select Provider (can be explicitly overridden)
        requested_provider = kwargs.pop("provider", None)
        disable_fallback = bool(kwargs.pop("disable_fallback", False))
        provider_name = requested_provider or self.routing_config.get(task, self.default_provider)
        provider = self.providers.get(provider_name)

        if not provider:
            logger.error(f"Provider {provider_name} not found for task {task}. Falling back to default.")
            provider = self.providers.get(self.default_provider)

        if not provider:
            raise ValueError(f"No LLM provider available for task {task}")

        # 3. Build Request
        # Filter kwargs into known fields and extras
        req_kwargs = {}
        extra_kwargs = {}
        
        # Pydantic v1 uses __fields__, v2 uses model_fields
        known_keys = LLMRequest.model_fields.keys() if hasattr(LLMRequest, "model_fields") else LLMRequest.__fields__.keys()
        
        for k, v in kwargs.items():
            if k in known_keys:
                req_kwargs[k] = v
            else:
                extra_kwargs[k] = v

        # Apply per-task default model unless caller explicitly provided one.
        explicit_model = extra_kwargs.get("model") or extra_kwargs.get("llm_model")
        if not explicit_model:
            configured_model = self.task_model_config.get(task)
            if configured_model:
                extra_kwargs["model"] = configured_model

        request = LLMRequest(
            task=task,
            messages=normalized_messages,
            extra_params=extra_kwargs,
            **req_kwargs
        )

        # 4. Execute with simple fallback logic
        try:
            return await provider.generate(request)
        except Exception as e:
            if disable_fallback:
                raise
            logger.warning(f"Primary provider {provider_name} failed for task {task}: {e}. Attempting fallback...")
            return await self._execute_fallback(request, provider_name)

    def update_routing_config(self, config: Dict[LLMTask, str]):
        """
        Updates the internal routing configuration.
        """
        self.routing_config = config
        logger.info(f"LLM Routing configuration updated: {config}")

    def update_task_model_config(self, config: Dict[LLMTask, Optional[str]]):
        """
        Updates per-task default model selection.
        """
        self.task_model_config = config
        logger.info(f"LLM task model config updated: {config}")

    async def _execute_fallback(self, request: LLMRequest, failed_provider: str) -> LLMResponse:
        """
        Simple fallback: try the first healthy provider that isn't the failed one.
        """
        for name, provider in self.providers.items():
            if name != failed_provider and provider.is_healthy():
                try:
                    logger.info(f"Retrying task {request.task} with fallback provider: {name}")
                    return await provider.generate(request)
                except Exception as e:
                    logger.error(f"Fallback provider {name} also failed: {e}")
                    continue
        
        raise RuntimeError(f"All LLM providers failed for task {request.task}")
