def commentary_schema() -> dict:
    citation = {
        "type": "object", "additionalProperties": False,
        "required": ["source_id", "start_ms", "end_ms", "quote"],
        "properties": {
            "source_id": {"type": "string", "minLength": 1},
            "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1},
            "quote": {"type": "string", "minLength": 1},
        },
    }
    return {
        "type": "object", "additionalProperties": False,
        "required": ["title", "sentences"],
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "sentences": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["text", "citations"],
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "citations": {"type": "array", "minItems": 1, "items": citation},
                },
            }},
        },
    }
