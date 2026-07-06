from typing import Any, Dict

from pydantic import BaseModel, Field


class Settings(BaseModel):
    s3accesskey: str
    s3secretkey: str
    s3endpoint: str

    yolo_infer_host: str = ""
    yolo_infer_port: int = 8022
    yolo_conf: float = 0.4
    yolo_model: str = "yolo11s.pt"
    yolo_presign_ttl: int = 3600
    detection_sidecar_prefix: str = "detections/"
    detection_store_frames: bool = True

    vdbendpoint: str = ""
    vdbbucket: str = ""
    vdbschema: str = ""
    vdbaccesskey: str = ""
    vdbsecretkey: str = ""
    vdbcollection: str = ""

    @classmethod
    def from_ctx_secrets(cls, secrets: Dict[str, Any]) -> "Settings":
        raw = secrets["vss2-secret"]
        config = {field: raw[field] for field in cls.__annotations__.keys() if field in raw}
        return cls(**config)
