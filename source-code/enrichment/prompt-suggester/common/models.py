from typing import Any, Dict, List

from pydantic import BaseModel


class Settings(BaseModel):
    """Configuration from DataEngine secret `vss2-secret`."""

    vdbendpoint: str
    vdbbucket: str
    vdbschema: str
    vdbaccesskey: str
    vdbsecretkey: str
    vdbcollection: str = "vss2-collection"
    vdbpromptscollection: str = "vss2-prompts-events"

    cosmos_host: str = ""
    cosmos_port: int = 8001
    cosmos_model: str = ""
    cosmos_max_tokens: int = 3000
    cosmos_temperature: float = 0.3

    suggestions_max_segments: int = 100
    suggestions_search_count: int = 10
    suggestions_events_count: int = 25
    suggestions_lookback_hours: int = 168

    @classmethod
    def from_ctx_secrets(cls, secrets: Dict[str, Any]) -> "Settings":
        raw = secrets["vss2-secret"]
        config = {field: raw[field] for field in cls.__annotations__.keys() if field in raw}
        return cls(**config)

    @property
    def cosmos_url(self) -> str:
        return f"http://{self.cosmos_host}:{self.cosmos_port}/v1/chat/completions"


class KeyEventSuggestion(BaseModel):
    """LLM output row for dashboard key events."""

    query_text: str
    label: str = ""
    original_video: str = ""
    filename: str = ""
    segment_start_sec: float = 0.0
    segment_end_sec: float = 0.0


class SuggestionsResult(BaseModel):
    """Parsed LLM JSON for one scheduled run."""

    search_prompts: List[str] = []
    key_events: List[KeyEventSuggestion] = []
