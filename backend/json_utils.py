import json
import re
import logging
from json_repair import repair_json

logger = logging.getLogger(__name__)

def extract_json(text: str) -> dict:
    """Извлекает JSON из ответа LLM, пробуя repair_json при ошибке."""
    # 1. Ищем ```json ... ```
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # 2. Ищем JSON-объект, который содержит ключ "narration"
        match = re.search(r'(\{"narration"\s*:.*\})', text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # 3. Ищем первую '{' и последнюю '}'
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group()
            else:
                raise ValueError("JSON not found")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            repaired = repair_json(json_str)
            return json.loads(repaired)
        except Exception as e:
            logger.error(f"JSON repair failed: {e}")
            raise ValueError("Broken JSON")