"""
Metadata discovery API endpoints for dynamic filtering
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
import logging

from src.models.user import User
from src.services.auth_service import get_current_user
from src.services.vastdb_service import get_vastdb_service
from src.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)

# User-facing upload metadata only (hide pipeline / perception / audit columns from GUI filters).
FILTERABLE_METADATA_COLUMNS = ("camera_id", "capture_type", "location")

METADATA_FIELD_LABELS = {
    "camera_id": "Camera ID",
    "capture_type": "Capture Type",
    "location": "Location",
}

# Internal columns — never exposed in Advanced Filters (also blocks /metadata/values).
_EXCLUDED_METADATA_COLUMNS = {
    "pk",
    "vectors",
    "vectors_visual",
    "source",
    "filename",
    "reasoning_content",
    "dense_caption",
    "vlm_structured",
    "structured_parse_ok",
    "perception_json",
    "object_classes",
    "object_counts",
    "max_detection_conf",
    "perception_ok",
    "extra_metadata",
    "cosmos_model",
    "embedding_model",
    "visual_embedding_model",
    "tokens_used",
    "cached_prompt_tokens",
    "processing_time",
    "timestamp",
    "upload_timestamp",
    "duration",
    "segment_number",
    "total_segments",
    "segment_start_sec",
    "segment_end_sec",
    "original_video",
    "tags",
    "allowed_users",
    "is_public",
}


@router.get("/schema")
async def get_metadata_schema(
    current_user: User = Depends(get_current_user)
):
    """
    Discover VastDB table schema dynamically
    Returns filterable metadata columns with their types
    
    This enables the frontend to build dynamic filter UI
    """
    try:
        vastdb_service = get_vastdb_service()
        
        settings = get_settings()
        logger.info(f"[METADATA] Discovering schema for table: {settings.vdb_collection}")
        
        arrow_schema = vastdb_service.get_table_schema()
        schema_by_name = {field.name: field for field in arrow_schema}

        schema = []

        for col_name in FILTERABLE_METADATA_COLUMNS:
            field = schema_by_name.get(col_name)
            if field is None:
                continue

            col_type = str(field.type)
            if "fixed_size_list" in col_type or "list<" in col_type:
                continue

            field_info = {
                "name": col_name,
                "type": col_type,
                "ui_type": "select",
                "label": METADATA_FIELD_LABELS.get(col_name, col_name.replace("_", " ").title()),
            }
            
            # Get distinct values for dropdown options
            try:
                distinct_values = vastdb_service.get_distinct_values(col_name)
                if distinct_values and len(distinct_values) > 0 and len(distinct_values) <= 100:
                    # Has predefined values - use dropdown
                    field_info["options"] = distinct_values
                    field_info["ui_type"] = "select"
                else:
                    # No values or too many - use text input
                    # This is expected for free-form fields like camera_id, location
                    field_info["ui_type"] = "text"
                    logger.info(f"[METADATA] Column {col_name} will use text input (no predefined values)")
            except Exception as e:
                logger.warning(f"Failed to get distinct values for {col_name}: {e}")
                field_info["ui_type"] = "text"  # Fallback to text input
            
            schema.append(field_info)
        
        logger.info(f"[METADATA] Returning {len(schema)} filterable columns: {[s['name'] for s in schema]}")
        
        return {
            "schema": schema,
            "table": settings.vdb_collection
        }
        
    except Exception as e:
        logger.error(f"[METADATA] Failed to discover schema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover metadata schema: {str(e)}"
        )


@router.get("/values")
async def get_field_values(
    field: str,
    prefix: str = "",
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    Get autocomplete suggestions for a specific field
    
    Args:
        field: Column name
        prefix: Optional prefix to filter values (for autocomplete)
        limit: Maximum number of values to return
    """
    try:
        vastdb_service = get_vastdb_service()
        
        logger.info(f"[METADATA] Getting values for field: {field}, prefix: {prefix}")
        
        if field in _EXCLUDED_METADATA_COLUMNS or field not in FILTERABLE_METADATA_COLUMNS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{field}' is not available for value lookup"
            )
        
        # Get distinct values
        values = vastdb_service.get_distinct_values(field, prefix=prefix, limit=limit)
        
        logger.info(f"[METADATA] Returned {len(values)} values for {field}")
        
        return {
            "field": field,
            "values": values,
            "count": len(values)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[METADATA] Failed to fetch field values: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch field values: {str(e)}"
        )

