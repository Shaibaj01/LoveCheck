import logging
import time
import base64
from typing import Dict, Any, Optional
import requests
import boto3
from opentelemetry import trace

from .prompts import get_prompt_for_scenario
from .structured_output import process_vlm_response, wrap_prompt_with_structured_output


def _safe_non_negative_int(value: Any) -> int:
    """
    Best-effort int coercion for usage fields.
    Returns 0 for missing, invalid, NaN/inf, or negative values.
    """
    try:
        parsed = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0
    return parsed if parsed > 0 else 0


def extract_usage_token_metrics(usage: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """
    OpenAI-compatible usage: total_tokens and input-side tokens served from prefix/KV cache.
    Reported as usage.prompt_tokens_details.cached_tokens — "prompt" here means full model
    input (instructions plus multimodal/video context), not text-only.
    """
    if not usage:
        return {"total_tokens": 0, "cached_prompt_tokens": 0}
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if total is None and (pt is not None or ct is not None):
        total = _safe_non_negative_int(pt) + _safe_non_negative_int(ct)
    total_i = _safe_non_negative_int(total)
    cached = 0
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        cached = _safe_non_negative_int(details.get("cached_tokens"))
    if cached == 0:
        cached = _safe_non_negative_int(usage.get("cached_tokens"))
    return {"total_tokens": total_i, "cached_prompt_tokens": cached}


class S3Client:
    """S3 client for downloading videos"""
    
    def __init__(self, settings):
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3endpoint,
            aws_access_key_id=settings.s3accesskey,
            aws_secret_access_key=settings.s3secretkey,
            verify=False
        )
    
    def download_file(self, bucket: str, key: str) -> bytes:
        """Download file from S3"""
        logging.info(f"[S3_CLIENT] Downloading s3://{bucket}/{key}")
        response = self.client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read()
        logging.info(f"[S3_CLIENT] Downloaded {len(content)} bytes")
        return content
    
    def head_object(self, bucket: str, key: str) -> Dict[str, Any]:
        """Get object metadata from S3"""
        logging.info(f"[S3_CLIENT] Fetching metadata for s3://{bucket}/{key}")
        response = self.client.head_object(Bucket=bucket, Key=key)
        logging.info(f"[S3_CLIENT] Retrieved metadata: {response.get('Metadata', {})}")
        return response


class CosmosReasoningClient:
    """Cosmos reasoning client for video analysis using hosted Reason2 API"""

    def __init__(self, settings):
        """Initialize Cosmos reasoning client"""
        self.settings = settings
        self.cosmos_url = settings.cosmos_url
        self.session = requests.Session()
        
        # Initialize tracer
        self.tracer = trace.get_tracer(__name__)

    def get_cosmos_reasoning(
        self,
        video_content: bytes,
        prompt: str = "Describe the main events in this clip.",
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get reasoning content from Cosmos API using base64-encoded video"""
        with self.tracer.start_as_current_span("Cosmos Reasoning API Call") as span:
            span.set_attributes({
                "cosmos_url": self.cosmos_url,
                "model": self.settings.cosmos_model,
                "video_size_bytes": len(video_content)
            })
            
            # Encode video to base64
            start_encode = time.time()
            video_base64 = base64.b64encode(video_content).decode()
            encode_time = time.time() - start_encode
            video_size_mb = len(video_content) / (1024 * 1024)
            base64_size_kb = len(video_base64) / 1024
            
            span.set_attributes({
                "video_size_mb": video_size_mb,
                "base64_size_kb": base64_size_kb,
                "encode_time_seconds": encode_time
            })
            
            logging.info(f"[COSMOS] Encoding video ({video_size_mb:.2f} MB) to base64 ({base64_size_kb:.1f} KB)...")
            
            # Prepare content with base64-encoded video
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "video_url",
                    "video_url": {
                        "url": f"data:video/mp4;base64,{video_base64}"
                    }
                }
            ]
            
            payload = {
                "model": self.settings.cosmos_model,
                "messages": [{
                    "role": "user",
                    "content": content
                }],
                "max_tokens": max_tokens if max_tokens is not None else self.settings.cosmos_max_tokens,
                "temperature": self.settings.cosmos_temperature
            }
            
            headers = {"Content-Type": "application/json"}
            token = (self.settings.cosmos_authorization or "").strip()
            if token:
                headers["Authorization"] = (
                    token if token.lower().startswith("bearer ") else f"Bearer {token}"
                )
            
            # Retry with exponential backoff
            max_retries = 3
            retry_delay = 2
            
            start_time = time.time()
            response = None
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    
                    response = self.session.post(
                        self.cosmos_url,
                        headers=headers,
                        json=payload,
                        timeout=600  # 10 minute timeout for large videos
                    )
                    break
                    
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt == max_retries - 1:
                        raise RuntimeError(f"Request failed after {max_retries} attempts: {e}")
            
            reasoning_time = time.time() - start_time
            span.set_attributes({
                "reasoning_time_seconds": reasoning_time,
                "http_status_code": response.status_code
            })
            
            if response.status_code != 200:
                error_text = response.text[:1000] if hasattr(response, 'text') else str(response.status_code)
                raise RuntimeError(f"Cosmos API error ({response.status_code}): {error_text}")
            
            response_data = response.json()
            
            choices = response_data.get("choices", [])
            if not choices:
                raise RuntimeError("No choices in Cosmos API response")
            
            reasoning_content = choices[0].get("message", {}).get("content", "")
            usage = response_data.get("usage") or {}
            metrics = extract_usage_token_metrics(usage)
            tokens_used = metrics["total_tokens"]
            cached_prompt_tokens = metrics["cached_prompt_tokens"]

            span.set_attributes({
                "reasoning_content_length": len(reasoning_content),
                "tokens_used": tokens_used,
                "cached_prompt_tokens": cached_prompt_tokens,
            })

            cache_note = f", {cached_prompt_tokens} cached input (API prompt_tokens_details)" if cached_prompt_tokens else ""
            logging.info(
                f"[COSMOS] {self.settings.cosmos_model} | {len(reasoning_content)} chars, "
                f"{tokens_used} tokens{cache_note} | {reasoning_time:.2f}s"
            )

            return {
                "reasoning_content": reasoning_content,
                "tokens_used": tokens_used,
                "cached_prompt_tokens": cached_prompt_tokens,
                "processing_time": reasoning_time,
                "cosmos_model": self.settings.cosmos_model,
                "raw_response": response_data
            }

    def analyze_video(
        self,
        video_content: bytes,
        filename: str,
        prompt: Optional[str] = None,
        scenario: Optional[str] = None,
        perception_context: Optional[str] = None,
        perception: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Complete video analysis pipeline using Cosmos reasoning.
        
        Args:
            video_content: Video file content as bytes
            filename: Name of the video file
            prompt: Optional custom prompt (overrides scenario)
            scenario: Optional scenario name (overrides settings default, ignored if prompt is provided)
            perception_context: Optional verified object summary prepended to the prompt
        """
        if prompt is None:
            scenario_to_use = scenario if scenario else self.settings.scenario
            prompt = get_prompt_for_scenario(scenario_to_use)
        else:
            prompt = wrap_prompt_with_structured_output(prompt)
        if perception_context:
            prompt = perception_context + prompt
        
        with self.tracer.start_as_current_span("Complete Video Analysis (Cosmos)") as span:
            scenario_used = scenario if scenario else self.settings.scenario
            span.set_attributes({
                "filename": filename,
                "file_size_bytes": len(video_content),
                "scenario": scenario_used
            })
            
            # Check video size limit
            max_size_bytes = self.settings.max_video_size_mb * 1024 * 1024
            if len(video_content) > max_size_bytes:
                raise ValueError(f"Video too large: {len(video_content)} > {max_size_bytes} bytes")
            
            # Send base64-encoded video directly to API (no SFTP upload)
            reasoning_result = self.get_cosmos_reasoning(video_content, prompt)
            structured = process_vlm_response(reasoning_result["reasoning_content"], perception=perception)
            
            result = {
                "filename": filename,
                "reasoning_content": structured["reasoning_content"],
                "dense_caption": structured["dense_caption"],
                "vlm_structured": structured["vlm_structured"],
                "structured_parse_ok": structured["structured_parse_ok"],
                "cosmos_model": reasoning_result["cosmos_model"],
                "tokens_used": reasoning_result["tokens_used"],
                "cached_prompt_tokens": reasoning_result.get("cached_prompt_tokens", 0),
                "processing_time": reasoning_result["processing_time"],
            }

            span.set_attributes({
                "reasoning_content_length": len(result["reasoning_content"]),
                "dense_caption_length": len(result["dense_caption"]),
                "structured_parse_ok": result["structured_parse_ok"],
                "total_tokens": result["tokens_used"],
                "cached_prompt_tokens": result["cached_prompt_tokens"],
                "total_processing_time": result["processing_time"]
            })
            
            return result

    def close(self):
        """Close HTTP session"""
        if hasattr(self, 'session'):
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

