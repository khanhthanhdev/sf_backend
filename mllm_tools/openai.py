import os
from typing import List, Dict, Any, Optional, Union, AsyncIterator
import asyncio

import litellm
from litellm import completion, acompletion, completion_cost
from dotenv import load_dotenv

# Load environment variables (CLI and apps use .env
load_dotenv()


class OpenAIWrapper:
    """Comprehensive OpenAI wrapper using LiteLLM following official docs.

    Features:
    - Uses OPENAI_API_KEY from environment (can be overridden via api_key argument)
    - Supports OPENAI_BASE_URL and OPENAI_ORGANIZATION environment variables
    - Handles reasoning models (o1/o3) with reasoning_effort instead of temperature
    - Supports streaming, function calling, and async operations
    - Proper error handling and cost tracking
    - Vision model support for image inputs
    """

    def __init__(
        self,
        model_name: str = "o3-mini",
        temperature: float = 0.7,
        print_cost: bool = False,
        verbose: bool = False,
        use_langfuse: bool = True,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 5,
    ):
        self.model_name = model_name
        self.model_name = model_name
        self.temperature = temperature
        self.print_cost = print_cost
        self.verbose = verbose
        self.max_retries = max_retries
        self.accumulated_cost = 0.0

        # Set up API key from environment or parameter
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is required. Set it as environment variable or pass as api_key parameter."
            )
        os.environ["OPENAI_API_KEY"] = key

        # Set optional environment variables following LiteLLM docs
        if base_url or os.getenv("OPENAI_BASE_URL"):
            os.environ["OPENAI_BASE_URL"] = base_url or os.getenv("OPENAI_BASE_URL")
        
        if organization or os.getenv("OPENAI_ORGANIZATION"):
            os.environ["OPENAI_ORGANIZATION"] = organization or os.getenv("OPENAI_ORGANIZATION")

        # Configure logging
        if verbose:
            os.environ["LITELLM_LOG"] = "DEBUG"
        
        # Configure callbacks for observability
        if use_langfuse:
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]

    def _is_reasoning_model(self) -> bool:
        """Check if model is a reasoning model (o1/o3 series)."""
        name = self.model_name.lower()
        return any(pattern in name for pattern in ["o1", "o3"])

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format messages to OpenAI chat completion format."""
        formatted_messages: List[Dict[str, Any]] = []
        
        # Handle simple text format conversion
        if messages and isinstance(messages[0], dict) and "type" in messages[0]:
            for msg in messages:
                if msg.get("type") == "text":
                    formatted_messages.append({
                        "role": "user",
                        "content": msg.get("content", "")
                    })
                elif msg.get("type") == "image_url":
                    # Support vision models
                    formatted_messages.append({
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": msg.get("text", "What's in this image?")},
                            {"type": "image_url", "image_url": {"url": msg.get("content", "")}}
                        ]
                    })
                else:
                    raise ValueError(f"Unsupported message type: {msg.get('type')}")
        else:
            # Assume messages are already in chat format
            formatted_messages = messages
            
        return formatted_messages

    def _calculate_cost(self, response) -> float:
        """Calculate and track cost of completion."""
        try:
            cost = completion_cost(completion_response=response) or 0.0
            self.accumulated_cost += float(cost)
            if self.print_cost:
                print(f"Request Cost: ${cost:.6f}")
                print(f"Accumulated Cost: ${self.accumulated_cost:.6f}")
            return float(cost)
        except Exception as e:
            if self.verbose:
                print(f"Cost calculation failed: {e}")
            return 0.0

    def __call__(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """Make a completion request to OpenAI via LiteLLM."""
        if metadata is None:
            metadata = {}
        metadata["trace_name"] = f"openai-completion-{self.model_name}"

        # Format messages to proper chat format
        formatted_messages = self._format_messages(messages)

        # Build parameters for completion
        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "metadata": metadata,
            "max_retries": kwargs.pop("max_retries", self.max_retries),
            "stream": stream,
        }

        # Add tools if provided
        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice

        # Handle reasoning vs regular models
        if self._is_reasoning_model():
            # Reasoning models use reasoning_effort instead of temperature
            params["reasoning_effort"] = kwargs.pop("reasoning_effort", "medium")
        else:
            params["temperature"] = kwargs.pop("temperature", self.temperature)

        # Add any additional parameters
        params.update(kwargs)

        try:
            response = completion(**params)
            
            # Calculate cost
            self._calculate_cost(response)
            
            # Handle streaming vs non-streaming
            if stream:
                return response  # Return the stream object
            
            # Handle function calling vs regular completion
            if tools and response.choices[0].message.tool_calls:
                return {
                    "content": response.choices[0].message.content,
                    "tool_calls": response.choices[0].message.tool_calls,
                    "response": response
                }
            
            # Regular text completion
            return response.choices[0].message.content or ""
            
        except Exception as e:
            error_msg = f"OpenAI completion failed: {str(e)}"
            if self.verbose:
                print(error_msg)
            raise Exception(error_msg) from e

    async def acompletion(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> Union[str, Dict[str, Any], AsyncIterator]:
        """Async completion request to OpenAI via LiteLLM."""
        if metadata is None:
            metadata = {}
        metadata["trace_name"] = f"openai-acompletion-{self.model_name}"

        # Format messages to proper chat format
        formatted_messages = self._format_messages(messages)

        # Build parameters for completion
        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "metadata": metadata,
            "max_retries": kwargs.pop("max_retries", self.max_retries),
            "stream": stream,
        }

        # Add tools if provided
        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice

        # Handle reasoning vs regular models
        if self._is_reasoning_model():
            params["reasoning_effort"] = kwargs.pop("reasoning_effort", "medium")
        else:
            params["temperature"] = kwargs.pop("temperature", self.temperature)

        # Add any additional parameters
        params.update(kwargs)

        try:
            response = await acompletion(**params)
            
            # Calculate cost
            self._calculate_cost(response)
            
            # Handle streaming vs non-streaming
            if stream:
                return response  # Return the async stream object
            
            # Handle function calling vs regular completion
            if tools and response.choices[0].message.tool_calls:
                return {
                    "content": response.choices[0].message.content,
                    "tool_calls": response.choices[0].message.tool_calls,
                    "response": response
                }
            
            # Regular text completion
            return response.choices[0].message.content or ""
            
        except Exception as e:
            error_msg = f"OpenAI async completion failed: {str(e)}"
            if self.verbose:
                print(error_msg)
            raise Exception(error_msg) from e

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Simple chat interface for text-only conversations."""
        result = self(messages, **kwargs)
        return result if isinstance(result, str) else result.get("content", "")

    def vision(self, text: str, image_url: str, **kwargs) -> str:
        """Simple vision interface for image analysis."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
        return self.chat(messages, **kwargs)


def create_openai_wrapper(model_name: str = "gpt-4o", **kwargs) -> OpenAIWrapper:
    """Factory function to create OpenAI wrapper instance."""
    return OpenAIWrapper(model_name=model_name, **kwargs)


# Updated with latest models from LiteLLM docs as of Sept 2025
AVAILABLE_MODELS = {
    # Latest models
    "gpt-5": "gpt-5",
    "gpt-5-mini": "gpt-5-mini", 
    "gpt-5-nano": "gpt-5-nano",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1-nano": "gpt-4.1-nano",
    
    # Reasoning models
    "o4-mini": "o4-mini",
    "o3": "o3",
    "o3-mini": "o3-mini",
    "o1-preview": "o1-preview",
    "o1-mini": "o1-mini",
    
    # Current production models
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o-2024-08-06": "gpt-4o-2024-08-06",
    "gpt-4o-2024-05-13": "gpt-4o-2024-05-13",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini-2024-07-18",
    
    # GPT-4 variants
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4-turbo-preview": "gpt-4-turbo-preview",
    "gpt-4": "gpt-4",
    "gpt-4-0125-preview": "gpt-4-0125-preview",
    "gpt-4-1106-preview": "gpt-4-1106-preview",
    "gpt-4-0613": "gpt-4-0613",
    "gpt-4-0314": "gpt-4-0314",
    "gpt-4-32k": "gpt-4-32k",
    "gpt-4-32k-0613": "gpt-4-32k-0613",
    "gpt-4-32k-0314": "gpt-4-32k-0314",
    
    # GPT-3.5 variants
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "gpt-3.5-turbo-1106": "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0613": "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo-0301": "gpt-3.5-turbo-0301",
    "gpt-3.5-turbo-16k": "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-16k-0613": "gpt-3.5-turbo-16k-0613",
    
    # Vision models
    "gpt-4-vision-preview": "gpt-4-vision-preview",
    
    # Audio models
    "whisper-1": "whisper-1",
    "gpt-4o-transcribe": "gpt-4o-transcribe",
    "gpt-4o-mini-transcribe": "gpt-4o-mini-transcribe",
}


# Helper functions for common use cases
def quick_chat(message: str, model: str = "gpt-4o", **kwargs) -> str:
    """Quick one-shot chat completion."""
    wrapper = create_openai_wrapper(model, **kwargs)
    messages = [{"role": "user", "content": message}]
    return wrapper.chat(messages)


def quick_vision(text: str, image_url: str, model: str = "gpt-4o", **kwargs) -> str:
    """Quick vision analysis."""
    wrapper = create_openai_wrapper(model, **kwargs)
    return wrapper.vision(text, image_url, **kwargs)


async def aquick_chat(message: str, model: str = "gpt-4o", **kwargs) -> str:
    """Quick async one-shot chat completion."""
    wrapper = create_openai_wrapper(model, **kwargs)
    messages = [{"role": "user", "content": message}]
    result = await wrapper.acompletion(messages, **kwargs)
    return result if isinstance(result, str) else result.get("content", "")

