import os
from dotenv import load_dotenv
from .aws_config import load_aws_config, AWSConfig
from typing import Optional

# Load environment variables from .env file
load_dotenv()

class Config:
    OUTPUT_DIR = "output"
    THEOREMS_PATH = os.path.join("data", "easy_20.json")
    CONTEXT_LEARNING_PATH = "data/context_learning"
    CHROMA_DB_PATH = "data/rag/chroma_db"
    MANIM_DOCS_PATH = "data/rag/manim_docs"
    EMBEDDING_MODEL = "hf:ibm-granite/granite-embedding-30m-english"
    
    # Kokoro TTS configurations
    KOKORO_MODEL_PATH = os.getenv('KOKORO_MODEL_PATH')
    KOKORO_VOICES_PATH = os.getenv('KOKORO_VOICES_PATH')
    KOKORO_DEFAULT_VOICE = os.getenv('KOKORO_DEFAULT_VOICE')
    KOKORO_DEFAULT_SPEED = float(os.getenv('KOKORO_DEFAULT_SPEED', '1.0'))
    KOKORO_DEFAULT_LANG = os.getenv('KOKORO_DEFAULT_LANG')
    
    # AWS Configuration
    _aws_config: Optional[AWSConfig] = None
    
    @classmethod
    def get_aws_config(cls, environment: Optional[str] = None) -> AWSConfig:
        """Get AWS configuration, loading it if not already cached"""
        if cls._aws_config is None:
            cls._aws_config = load_aws_config(environment)
        return cls._aws_config
    
    @classmethod
    def reload_aws_config(cls, environment: Optional[str] = None) -> AWSConfig:
        """Reload AWS configuration (useful for testing or config changes)"""
        cls._aws_config = load_aws_config(environment)
        return cls._aws_config 