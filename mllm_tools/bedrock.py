import os
from typing import List, Dict, Any, Optional, Union, AsyncIterator
import asyncio
import base64

import litellm
from litellm import completion, acompletion, completion_cost, embedding, image_generation, rerank
from dotenv import load_dotenv

# Load environment variables (CLI and apps use .env)
load_dotenv(override=True)


class BedrockWrapper:
    """Comprehensive AWS Bedrock wrapper using LiteLLM following official docs.

    Features:
    - Uses AWS credentials from environment (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME)
    - Supports all Bedrock model types: Anthropic Claude, Meta Llama, Amazon Titan, etc.
    - Handles function calling, vision, streaming, and async operations
    - Supports Bedrock-specific features like guardrails, cross-region inference
    - Proper error handling and cost tracking
    - Support for embeddings, image generation, and reranking
    """

    def __init__(
        self,
        model_name: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
        temperature: float = 0.7,
        print_cost: bool = False,
        verbose: bool = False,
        use_langfuse: bool = True,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region_name: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        aws_profile_name: Optional[str] = None,
        aws_role_name: Optional[str] = None,
        aws_session_name: Optional[str] = None,
        aws_bedrock_runtime_endpoint: Optional[str] = None,
        max_retries: int = 5,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.print_cost = print_cost
        self.verbose = verbose
        self.max_retries = max_retries
        self.accumulated_cost = 0.0

        # Set up AWS credentials from environment or parameters
        self._setup_aws_credentials(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name,
            aws_session_token=aws_session_token,
            aws_profile_name=aws_profile_name,
            aws_role_name=aws_role_name,
            aws_session_name=aws_session_name,
            aws_bedrock_runtime_endpoint=aws_bedrock_runtime_endpoint,
        )

        # Configure logging
        if verbose:
            os.environ["LITELLM_LOG"] = "DEBUG"
            litellm.set_verbose = True
        
        # Configure callbacks for observability
        if use_langfuse:
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]

    def _setup_aws_credentials(self, **kwargs):
        """Set up AWS credentials from parameters or environment variables."""
        # Required credentials
        access_key = kwargs.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = kwargs.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
        region = kwargs.get("aws_region_name") or os.getenv("AWS_REGION_NAME")

        if not all([access_key, secret_key, region]):
            raise ValueError(
                "AWS credentials are required. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
                "and AWS_REGION_NAME as environment variables or pass them as parameters."
            )

        # Set required environment variables
        os.environ["AWS_ACCESS_KEY_ID"] = access_key
        os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
        os.environ["AWS_REGION_NAME"] = region

        # Set optional environment variables
        optional_vars = {
            "AWS_SESSION_TOKEN": kwargs.get("aws_session_token"),
            "AWS_PROFILE": kwargs.get("aws_profile_name"),
            "AWS_ROLE_NAME": kwargs.get("aws_role_name"),
            "AWS_SESSION_NAME": kwargs.get("aws_session_name"),
            "AWS_BEDROCK_RUNTIME_ENDPOINT": kwargs.get("aws_bedrock_runtime_endpoint"),
        }

        for env_var, value in optional_vars.items():
            if value:
                os.environ[env_var] = value

    def _is_anthropic_model(self) -> bool:
        """Check if model is an Anthropic Claude model."""
        return "anthropic" in self.model_name.lower() or "claude" in self.model_name.lower()

    def _is_reasoning_model(self) -> bool:
        """Check if model supports reasoning features."""
        model_lower = self.model_name.lower()
        return any(pattern in model_lower for pattern in ["claude-3-7", "claude-4"])

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format messages to Bedrock chat completion format."""
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
                    # Support vision models - use proper format for Bedrock
                    formatted_messages.append({
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": msg.get("text", "What's in this image?")},
                            {"type": "image_url", "image_url": {"url": msg.get("content", "")}}
                        ]
                    })
                elif msg.get("type") == "file":
                    # For document understanding, convert to image_url format
                    # Bedrock expects document content as image_url with base64
                    file_info = msg.get("file", {})
                    file_data = file_info.get("file_data", "")
                    
                    formatted_messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": msg.get("text", "What's in this document?")},
                            {"type": "image_url", "image_url": {"url": file_data}}
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
        max_tokens: Optional[int] = None,
        guardrailConfig: Optional[Dict[str, Any]] = None,
        performanceConfig: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """Make a completion request to AWS Bedrock via LiteLLM."""
        if metadata is None:
            metadata = {}
        metadata["trace_name"] = f"bedrock-completion-{self.model_name}"

        # Format messages to proper chat format
        formatted_messages = self._format_messages(messages)

        # Build parameters for completion
        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "metadata": metadata,
            "max_retries": kwargs.pop("max_retries", self.max_retries),
            "stream": stream,
            "temperature": kwargs.pop("temperature", self.temperature),
        }

        # Add optional parameters
        if max_tokens:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice
        if guardrailConfig:
            params["guardrailConfig"] = guardrailConfig
        if performanceConfig:
            params["performanceConfig"] = performanceConfig
        if extra_headers:
            params["extra_headers"] = extra_headers

        # Handle reasoning models - Note: reasoning_effort is not supported in Bedrock
        # Remove this parameter if passed to avoid errors
        kwargs.pop("reasoning_effort", None)

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
                    "reasoning_content": getattr(response.choices[0].message, "reasoning_content", None),
                    "thinking_blocks": getattr(response.choices[0].message, "thinking_blocks", None),
                    "response": response
                }
            
            # Regular text completion
            content = response.choices[0].message.content or ""
            
            # Include reasoning content if available (for Claude 3.7+)
            result = {"content": content}
            if hasattr(response.choices[0].message, "reasoning_content"):
                result["reasoning_content"] = response.choices[0].message.reasoning_content
            if hasattr(response.choices[0].message, "thinking_blocks"):
                result["thinking_blocks"] = response.choices[0].message.thinking_blocks
            
            return content if len(result) == 1 else result
            
        except Exception as e:
            error_msg = f"Bedrock completion failed: {str(e)}"
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
        max_tokens: Optional[int] = None,
        guardrailConfig: Optional[Dict[str, Any]] = None,
        performanceConfig: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Union[str, Dict[str, Any], AsyncIterator]:
        """Async completion request to AWS Bedrock via LiteLLM."""
        if metadata is None:
            metadata = {}
        metadata["trace_name"] = f"bedrock-acompletion-{self.model_name}"

        # Format messages to proper chat format
        formatted_messages = self._format_messages(messages)

        # Build parameters for completion
        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "metadata": metadata,
            "max_retries": kwargs.pop("max_retries", self.max_retries),
            "stream": stream,
            "temperature": kwargs.pop("temperature", self.temperature),
        }

        # Add optional parameters
        if max_tokens:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice
        if guardrailConfig:
            params["guardrailConfig"] = guardrailConfig
        if performanceConfig:
            params["performanceConfig"] = performanceConfig
        if extra_headers:
            params["extra_headers"] = extra_headers

        # Handle reasoning models - Note: reasoning_effort is not supported in Bedrock
        # Remove this parameter if passed to avoid errors
        kwargs.pop("reasoning_effort", None)

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
                    "reasoning_content": getattr(response.choices[0].message, "reasoning_content", None),
                    "thinking_blocks": getattr(response.choices[0].message, "thinking_blocks", None),
                    "response": response
                }
            
            # Regular text completion
            content = response.choices[0].message.content or ""
            
            # Include reasoning content if available
            result = {"content": content}
            if hasattr(response.choices[0].message, "reasoning_content"):
                result["reasoning_content"] = response.choices[0].message.reasoning_content
            if hasattr(response.choices[0].message, "thinking_blocks"):
                result["thinking_blocks"] = response.choices[0].message.thinking_blocks
            
            return content if len(result) == 1 else result
            
        except Exception as e:
            error_msg = f"Bedrock async completion failed: {str(e)}"
            if self.verbose:
                print(error_msg)
            raise Exception(error_msg) from e

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Simple chat interface for text-only conversations."""
        result = self(messages, **kwargs)
        if isinstance(result, dict):
            return result.get("content", "")
        return result

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

    def document_understanding(self, text: str, file_data: str, filename: str = "document", **kwargs) -> str:
        """Simple document understanding interface."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {
                        "type": "file",
                        "file": {
                            "filename": filename,
                            "file_data": file_data
                        }
                    }
                ]
            }
        ]
        return self.chat(messages, **kwargs)

    def generate_embeddings(self, input_text: Union[str, List[str]], model: Optional[str] = None, **kwargs):
        """Generate embeddings using Bedrock embedding models."""
        embedding_model = model or "bedrock/amazon.titan-embed-text-v1"
        
        try:
            response = embedding(
                model=embedding_model,
                input=input_text if isinstance(input_text, list) else [input_text],
                **kwargs
            )
            return response
        except Exception as e:
            error_msg = f"Bedrock embedding failed: {str(e)}"
            if self.verbose:
                print(error_msg)
            raise Exception(error_msg) from e

    def generate_image(self, prompt: str, model: Optional[str] = None, **kwargs):
        """Generate images using Bedrock image generation models."""
        image_model = model or "bedrock/stability.stable-diffusion-xl-v1"
        
        try:
            response = image_generation(
                prompt=prompt,
                model=image_model,
                **kwargs
            )
            return response
        except Exception as e:
            error_msg = f"Bedrock image generation failed: {str(e)}"
            if self.verbose:
                print(error_msg)
            raise Exception(error_msg) from e

    def rerank_documents(self, query: str, documents: List[str], model: Optional[str] = None, top_n: int = 5, **kwargs):
        """Rerank documents using Bedrock rerank models."""
        rerank_model = model or "bedrock/arn:aws:bedrock:us-west-2::foundation-model/amazon.rerank-v1:0"
        
        try:
            response = rerank(
                model=rerank_model,
                query=query,
                documents=documents,
                top_n=top_n,
                **kwargs
            )
            return response
        except Exception as e:
            error_msg = f"Bedrock rerank failed: {str(e)}"
            if self.verbose:
                print(error_msg)
            raise Exception(error_msg) from e


def create_bedrock_wrapper(model_name: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", **kwargs) -> BedrockWrapper:
    """Factory function to create Bedrock wrapper instance."""
    return BedrockWrapper(model_name=model_name, **kwargs)


# Available Bedrock models organized by provider
AVAILABLE_BEDROCK_MODELS = {
    # Anthropic Claude models
    "anthropic": {
        "claude-3-5-sonnet": "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
        "claude-3-5-sonnet-v2": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "claude-3-7-sonnet": "bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "claude-4": "bedrock/anthropic.claude-sonnet-4-20250115-v1:0",
        "claude-3-sonnet": "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
        "claude-3-haiku": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
        "claude-3-opus": "bedrock/anthropic.claude-3-opus-20240229-v1:0",
        "claude-v2": "bedrock/anthropic.claude-v2",
        "claude-v2.1": "bedrock/anthropic.claude-v2:1",
        "claude-instant-v1": "bedrock/anthropic.claude-instant-v1",
    },
    # Meta LLaMA models
    "meta": {
        "llama3-1-405b": "bedrock/meta.llama3-1-405b-instruct-v1:0",
        "llama3-1-70b": "bedrock/meta.llama3-1-70b-instruct-v1:0",
        "llama3-1-8b": "bedrock/meta.llama3-1-8b-instruct-v1:0",
        "llama3-70b": "bedrock/meta.llama3-70b-instruct-v1:0",
        "llama3-8b": "bedrock/meta.llama3-8b-instruct-v1:0",
        "llama2-13b": "bedrock/meta.llama2-13b-chat-v1",
        "llama2-70b": "bedrock/meta.llama2-70b-chat-v1",
    },
    # Amazon Titan models
    "amazon": {
        "titan-text-lite": "bedrock/amazon.titan-text-lite-v1",
        "titan-text-express": "bedrock/amazon.titan-text-express-v1",
        "titan-embed-text-v1": "bedrock/amazon.titan-embed-text-v1",
        "titan-embed-text-v2": "bedrock/amazon.titan-embed-text-v2:0",
        "titan-embed-image-v1": "bedrock/amazon.titan-embed-image-v1",
        "nova-pro": "bedrock/us.amazon.nova-pro-v1:0",
        "nova-lite": "bedrock/us.amazon.nova-lite-v1:0",
        "nova-micro": "bedrock/us.amazon.nova-micro-v1:0",
        "nova-canvas": "bedrock/amazon.nova-canvas-v1:0",
    },
    # Cohere models
    "cohere": {
        "command-text": "bedrock/cohere.command-text-v14",
        "command-r": "bedrock/cohere.command-r-v1:0",
        "command-r-plus": "bedrock/cohere.command-r-plus-v1:0",
        "embed-english": "bedrock/cohere.embed-english-v3",
        "embed-multilingual": "bedrock/cohere.embed-multilingual-v3",
    },
    # Mistral models
    "mistral": {
        "mistral-7b": "bedrock/mistral.mistral-7b-instruct-v0:2",
        "mixtral-8x7b": "bedrock/mistral.mixtral-8x7b-instruct-v0:1",
        "mistral-large": "bedrock/mistral.mistral-large-2402-v1:0",
    },
    # AI21 models
    "ai21": {
        "j2-mid": "bedrock/ai21.j2-mid-v1",
        "j2-ultra": "bedrock/ai21.j2-ultra-v1",
        "jamba-instruct": "bedrock/ai21.jamba-instruct-v1:0",
    },
    # Stability AI models
    "stability": {
        "stable-diffusion-xl-v0": "bedrock/stability.stable-diffusion-xl-v0",
        "stable-diffusion-xl-v1": "bedrock/stability.stable-diffusion-xl-v1",
        "sd3-large": "bedrock/stability.stability.sd3-large-v1:0",
    },
    # Deepseek models
    "deepseek": {
        "deepseek-r1": "bedrock/us.deepseek.r1-v1:0",
    },
    # OpenAI GPT OSS models
    "openai": {
        "gpt-oss-20b": "bedrock/converse/openai.gpt-oss-20b-1:0",
        "gpt-oss-120b": "bedrock/converse/openai.gpt-oss-120b-1:0",
    }
}


# Helper functions for common use cases
def quick_bedrock_chat(message: str, model: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", **kwargs) -> str:
    """Quick one-shot chat completion with Bedrock."""
    wrapper = create_bedrock_wrapper(model, **kwargs)
    messages = [{"role": "user", "content": message}]
    return wrapper.chat(messages)


def quick_bedrock_vision(text: str, image_url: str, model: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", **kwargs) -> str:
    """Quick vision analysis with Bedrock."""
    wrapper = create_bedrock_wrapper(model, **kwargs)
    return wrapper.vision(text, image_url, **kwargs)


def quick_bedrock_document(text: str, file_data: str, filename: str = "document", model: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", **kwargs) -> str:
    """Quick document understanding with Bedrock."""
    wrapper = create_bedrock_wrapper(model, **kwargs)
    return wrapper.document_understanding(text, file_data, filename, **kwargs)


async def aquick_bedrock_chat(message: str, model: str = "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", **kwargs) -> str:
    """Quick async one-shot chat completion with Bedrock."""
    wrapper = create_bedrock_wrapper(model, **kwargs)
    messages = [{"role": "user", "content": message}]
    result = await wrapper.acompletion(messages, **kwargs)
    return result if isinstance(result, str) else result.get("content", "")


def encode_image_to_base64(image_path: str) -> str:
    """Encode image file to base64 string for vision models."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def encode_document_to_base64(file_path: str) -> str:
    """Encode document file to base64 string for document understanding."""
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")
