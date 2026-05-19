# Dynamic Metadata Filters

The system supports customizable metadata fields that flow through the entire pipeline, enabling powerful filtering and organization of video content.

## Current Metadata Fields

The system currently supports four metadata fields:

- **`camera_id`** - Camera identifier (e.g., "cam-01", "intersection-5th-ave")
- **`capture_type`** - Type of capture (e.g., "traffic", "streets", "crowds", "malls")
- **`location`** - Location/area (e.g., "manhattan", "downtown", "warehouse-a")
- **`scenario`** - Analysis prompt scenario (e.g., "surveillance", "traffic", "egocentric", "general") — flows through S3 metadata only (not stored in VastDB)

**Structured VLM output (stored in VastDB per segment):**

- **`vlm_structured`** - JSON string with objects, actions, events, hazards
- **`dense_caption`** - Short canonical text used for vector embedding (search index)
- **`reasoning_content`** - Human-readable narrative for UI display
- **`structured_parse_ok`** - Whether JSON parsing succeeded for this segment

**Timeline and grouping (stored in VastDB per segment):**

- **`segment_start_sec`** / **`segment_end_sec`** - Position within the parent video (seconds from start)
- **`original_video`** - Canonical parent video S3 URI (`s3://bucket/key` of the source upload), used to group all segments from one ingest
- **`source`** - Segment clip S3 URI (unique per row)

## How It Works

The metadata flows through the entire system:

1. **Ingest**: Metadata is set when uploading videos (via GUI upload or streaming service)
2. **Pipeline**: Metadata propagates through all functions (segmenter → reasoner → embedder → writer)
3. **VastDB**: Stored as columns alongside vectors and reasoning content
4. **Backend**: Auto-discovers available metadata columns dynamically from VastDB schema
5. **Frontend**: Displays discovered filters as dropdowns with actual values from the database

## Adding Custom Metadata Fields

To add new metadata fields to the system:

### Step 1: Update Models in All Functions

Add the field to the metadata model in each function's `common/models.py`:

**Files to update:**
- `source-code/ingest/video-segmenter/common/models.py`
- `source-code/ingest/video-reasoner/common/models.py`
- `source-code/ingest/video-embedder/common/models.py`
- `source-code/ingest/vastdb-writer/common/models.py`

**Example:**
```python
class VideoMetadata(BaseModel):
    camera_id: Optional[str] = None
    capture_type: Optional[str] = None
    location: Optional[str] = None
    your_new_field: Optional[str] = None  # Add your new field here
```

### Step 2: Pass Metadata Through Function Handlers

Ensure each function's handler receives and passes the metadata:

- **video-segmenter**: Extract metadata from S3 object metadata or input event
- **video-reasoner**: Pass metadata from input to output
- **video-embedder**: Pass metadata from input to output
- **video-vastdb-writer**: Include metadata in the database write operation

### Step 3: Update VastDB Schema

Add the new field to the VastDB schema in `source-code/ingest/vastdb-writer/common/vastdb_client.py`:

```python
# In the schema definition
schema = {
    # ... existing columns ...
    "your_new_field": "VARCHAR(255)",  # Add your new column
}
```

### Step 4: Restart Backend

The backend automatically discovers metadata columns from the VastDB schema on startup. After adding a new field:

1. Ensure the field is in the VastDB schema (Step 3)
2. Restart the backend service
3. The new field will appear as a filter in the frontend automatically

## Using Metadata in the Frontend

Once metadata fields are configured:

1. **Upload with Metadata**: When uploading videos via GUI or [streaming service](../../video-streaming/README.md), set the metadata values
2. **Automatic Discovery**: The frontend automatically discovers available metadata fields from the database
3. **Filter Dropdowns**: Each metadata field appears as a filter dropdown in the search interface
4. **Dynamic Values**: Dropdown values are populated from actual data in the database

**Note:** The backend service automatically discovers metadata columns from the VastDB schema on startup. No manual configuration is needed in the frontend.

## Example Use Cases

- **Multi-Camera Systems**: Use `camera_id` to filter by specific cameras
- **Location-Based Search**: Use `location` to search within specific areas
- **Content Type Filtering**: Use `capture_type` to filter by video type (traffic, retail, etc.)
- **Custom Classifications**: Add fields like `priority`, `status`, `department` for custom workflows

## Best Practices

- **Use descriptive names**: Field names should be clear and self-documenting
- **Keep values consistent**: Use standardized values (e.g., lowercase, no spaces) for better filtering
- **Plan ahead**: Consider what metadata will be useful for search and filtering before deployment
- **Document your fields**: Keep track of what each metadata field represents and its possible values

