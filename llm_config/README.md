LLM Configuration

Purpose: Centralized configuration and helpers for LLM providers.

Key Class:
- provider_manager.py: `EnhancedProviderManager` exposes provider metadata, model lists, env var names, and helpers for setting keys and Bedrock credentials.

Environment:
- OpenAI: `OPENAI_API_KEY`
- Google Gemini: `GOOGLE_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- OpenRouter: `OPENROUTER_API_KEY`
- AWS Bedrock: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`

Example:
```python
from llm_config.provider_manager import EnhancedProviderManager

pm = EnhancedProviderManager()
pm.set_api_key('OpenAI', 'sk-...')
models = pm.get_models('OpenAI')
print(models)
```

Notes:
- Includes descriptions for models and providers for UI display.
- Validates presence of required env vars for Bedrock.

