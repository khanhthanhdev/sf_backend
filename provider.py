"""
Provider management for Theory2Manim tools.

This module provides a simple provider registry to manage API keys and
model selections for multiple LLM providers. It is intentionally
lightweight for UI integrations and scripting convenience.
"""

import os
from typing import Dict, List, Optional


class ProviderManager:
    """Simple provider manager responsible for API keys and model lists.

    Notes:
    - This provider manager is UI-friendly and geared for local tooling.
    - For the FastAPI backend, see `llm_config/enhanced_provider_manager.py`.
    """

    def __init__(self) -> None:
        # Provider configs; extend as needed
        self.providers: Dict[str, Dict[str, object]] = {
            'OpenAI': {
                'api_key_env': 'OPENAI_API_KEY',
                'models': [
                    'gpt-4.1', 'gpt-4o', 'gpt-3.5-turbo'
                ]
            },
            'Google Gemini': {
                'api_key_env': 'GOOGLE_API_KEY',
                'models': [
                    'gemini-1.5-pro-002', 'gemini-2.5-flash-preview-04-17'
                ]
            },
            'Anthropic': {
                'api_key_env': 'ANTHROPIC_API_KEY',
                'models': [
                    'claude-3-5-sonnet-20241022', 'claude-3-haiku'
                ]
            },
            'OpenRouter': {
                'api_key_env': 'OPENROUTER_API_KEY',
                'models': [
                    'openai/gpt-4o', 'openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet',
                    'anthropic/claude-3-haiku', 'google/gemini-pro-1.5', 'deepseek/deepseek-chat',
                    'qwen/qwen-2.5-72b-instruct', 'meta-llama/llama-3.1-8b-instruct:free',
                    'microsoft/phi-3-mini-128k-instruct:free'
                ]
            },
            'AWS Bedrock': {
                'api_key_env': 'AWS_ACCESS_KEY_ID',
                'models': [
                    'bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0',
                    'bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0',
                    'bedrock/anthropic.claude-3-5-haiku-20241022-v1:0',
                    'bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0',
                    'bedrock/anthropic.claude-sonnet-4-20250115-v1:0',
                    'bedrock/us.amazon.nova-pro-v1:0',
                    'bedrock/us.amazon.nova-lite-v1:0',
                    'bedrock/meta.llama3-1-405b-instruct-v1:0',
                    'bedrock/meta.llama3-1-70b-instruct-v1:0'
                ]
            }
        }
        self.selected_provider: Optional[str] = None
        self.api_keys: Dict[str, str] = {}

    def get_providers(self) -> List[str]:
        """Return available provider names."""
        return list(self.providers.keys())

    def get_models(self, provider: str) -> List[str]:
        """Return supported models for a given provider."""
        return self.providers.get(provider, {}).get('models', [])  # type: ignore[return-value]

    def set_api_key(self, provider: str, api_key: str) -> None:
        """Set and persist the API key for a provider via env var."""
        env_var = self.providers[provider]['api_key_env']  # type: ignore[index]
        os.environ[str(env_var)] = api_key
        self.api_keys[provider] = api_key

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get the API key for a provider from env."""
        env_var = self.providers[provider]['api_key_env']  # type: ignore[index]
        return os.environ.get(str(env_var))

    def get_selected_provider(self) -> Optional[str]:
        """Return the currently selected provider, if any."""
        return self.selected_provider

    def set_selected_provider(self, provider: str) -> None:
        """Set the current provider used by the app."""
        self.selected_provider = provider

    def get_selected_model(self) -> Optional[str]:
        """Return a default model for the selected provider, if any."""
        if self.selected_provider:
            models = self.get_models(self.selected_provider)
            return models[0] if models else None
        return None


provider_manager = ProviderManager()
