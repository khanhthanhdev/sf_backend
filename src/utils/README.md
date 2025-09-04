Utils

Purpose: Shared utility helpers and data for the video pipeline and API.

Files:
- utils.py: Helpers to extract code/JSON/XML from LLM responses and format outputs.
- allowed_models.json: Allowlist of models available to the CLI/app.

Example:
```python
from src.utils.utils import extract_json, extract_xml

data = extract_json(response_text)
xml = extract_xml(response_text)
```

Notes:
- `utils.py` functions are pure and easy to unit test.

