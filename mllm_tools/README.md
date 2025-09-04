MLLM Tools

Purpose: Wrappers around multiple LLM providers with consistent APIs for completions, embeddings, media, and utilities.

Key Modules:
- bedrock.py: `BedrockWrapper` for AWS Bedrock via LiteLLM (chat, async, embeddings, image, rerank). Requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`.
- gemini.py: `GeminiWrapper` for Google Gemini native API (text, vision, video).
- openrouter.py: `OpenRouterWrapper` for multi-provider routing through OpenRouter.
- vertex_ai.py: `VertexAIWrapper` for Google Vertex AI.
- utils.py: Helpers to prepare multimodal messages and media uploads.

Usage Example (Bedrock):
```python
from mllm_tools.bedrock import BedrockWrapper

llm = BedrockWrapper(model_name="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", verbose=True)
resp = llm([
    {"role": "user", "content": "Explain the Pythagorean theorem."}
])
print(resp)
```

Usage Example (Media Messages):
```python
from mllm_tools.utils import prepare_media_messages

messages = prepare_media_messages(
    prompt="What is in this image?",
    media_path="/path/to/image.jpg",
    model_name="gemini/gemini-1.5-pro-002"
)
```

Notes:
- Prefer provider-prefixed model names (e.g., `bedrock/...`, `gemini/...`, `openrouter/...`).
- See repository `.env.example` for required environment variables.

