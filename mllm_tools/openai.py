import os
from typing import List, Dict, Any, Optional

import litellm
from litellm import completion, completion_cost
from dotenv import load_dotenv

# Load environment variables (CLI and apps use .env)
load_dotenv(override=True)


class OpenAIWrapper:
    """Thin OpenAI wrapper using LiteLLM that reads OPENAI_API_KEY from env.

    - Uses OPENAI_API_KEY by default (can be overridden via api_key argument)
    - Optionally honors OPENAI_BASE_URL and OPENAI_ORGANIZATION
    - Supports temperature for non-reasoning models; o1/o3 omit temperature and use reasoning_effort
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
        print_cost: bool = False,
        verbose: bool = False,
        use_langfuse: bool = True,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.print_cost = print_cost
        self.verbose = verbose
        self.accumulated_cost = 0.0

        # Configure API key strictly from OPENAI_API_KEY unless explicitly passed
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI models")
        os.environ["OPENAI_API_KEY"] = key

        # Optional base URL and organization
        if base_url:
            os.environ["OPENAI_BASE_URL"] = base_url
        if organization:
            os.environ["OPENAI_ORGANIZATION"] = organization

        if verbose:
            os.environ["LITELLM_LOG"] = "DEBUG"
        if use_langfuse:
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]

    def _is_reasoning_model(self) -> bool:
        name = self.model_name.lower()
        return name.startswith("o1") or name.startswith("o3") or "/o1" in name or "/o3" in name

    def __call__(self, messages: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        if metadata is None:
            metadata = {}
        metadata["trace_name"] = f"openai-completion-{self.model_name}"

        # Expect messages in LiteLLM chat format already or simple text list
        # If messages are in our simple format [{'type':'text','content':'...'}], convert them
        formatted_messages: List[Dict[str, Any]] = []
        if messages and isinstance(messages[0], dict) and "type" in messages[0]:
            for msg in messages:
                if msg.get("type") == "text":
                    formatted_messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": msg.get("content", "")}]
                    })
                else:
                    raise ValueError("OpenAIWrapper supports only text messages in this wrapper")
        else:
            formatted_messages = messages  # assume already chat format

        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "metadata": metadata,
            "max_retries": kwargs.pop("max_retries", 5),
        }

        if self._is_reasoning_model():
            params["reasoning_effort"] = kwargs.pop("reasoning_effort", "medium")
        else:
            params["temperature"] = kwargs.pop("temperature", self.temperature)

        params.update(kwargs)

        try:
            resp = completion(**params)
            if self.print_cost:
                try:
                    cost = completion_cost(completion_response=resp) or 0.0
                    self.accumulated_cost += float(cost)
                    print(f"Accumulated Cost: ${self.accumulated_cost:.6f}")
                except Exception:
                    pass
            return getattr(resp.choices[0].message, "content", "")
        except Exception as e:
            return str(e)


def create_openai_wrapper(model_name: str = "gpt-4o", **kwargs) -> OpenAIWrapper:
    return OpenAIWrapper(model_name=model_name, **kwargs)


AVAILABLE_MODELS = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4": "gpt-4",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
}

