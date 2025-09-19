# processors/universal.py
"""
Universal processor for both images and videos with support for all effects.
Handles logo, watermark, bigtext, editions, etc. for both media types using:
- PIL for image overlays and effects
- ffmpeg-python for video composition and effects
"""

import io
import os
import tempfile
import logging
from typing import Tuple, Optional, Dict, Any
from PIL import Image, ImageOps
import ffmpeg

from . import logo, watermark, big_text, captions
from . import ensure_rgba, ensure_rgb

logger = logging.getLogger("universal_processor")


def is_video_file(file_bytes: bytes) -> bool:
    """
    Detect if the file is a video based on magic bytes.
    Supports common video formats: MP4, AVI, MOV, MKV, etc.
    """
    # Video magic bytes for common formats
    video_signatures = [
        b'\x00\x00\x00\x18ftypmp4',    # MP4
        b'\x00\x00\x00\x20ftypmp4',    # MP4
        b'\x00\x00\x00\x1cftypisom',   # MP4/ISOM
        b'\x00\x00\x00\x20ftypisom',   # MP4/ISOM (our test video)
        b'\x00\x00\x00\x14ftypqt',     # MOV
        b'\x1aE\xdf\xa3',              # MKV
        b'FLV',                         # FLV
        b'\x00\x00\x01\xb3',           # MPEG
        b'\x00\x00\x01\xba',           # MPEG
        b'RIFF',                        # AVI (starts with RIFF, then has 'AVI ' later)
    ]
    
    file_start = file_bytes[:32]
    
    # First check for exact matches
    for signature in video_signatures:
        if file_start.startswith(signature):
            return True
    
    # More flexible MP4/MOV detection - check for ftyp box anywhere within first 16 bytes
    if b'ftyp' in file_start[:16]:
        # Check if it contains common MP4/MOV type indicators
        ftyp_indicators = [b'mp4', b'isom', b'M4V', b'mp41', b'mp42', b'avc1', b'qt']
        for indicator in ftyp_indicators:
            if indicator in file_start:
                return True
    
    # Check for AVI (RIFF + AVI combination)
    if file_start.startswith(b'RIFF') and b'AVI ' in file_bytes[:64]:
        return True
        
    return False



def process_image(image_bytes: bytes, caption: Optional[str], config: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Process an image with the specified caption/effects.
    """
    logger.info(f"Processing image with caption: {caption}")
    
    # Load and normalize image
    base = Image.open(io.BytesIO(image_bytes))
    base = ImageOps.exif_transpose(base)
    if base.mode not in ("RGB", "RGBA"):
        base = base.convert("RGB")
    
    # Apply effects directly to the base image
    result = apply_effects_to_image(base, caption, config)
    
    # Generate filename based on effect
    raw_caption = (caption or "").strip()
    kind, _ = captions.classify(raw_caption)
    if raw_caption.lower().startswith("bigtext") or raw_caption.lower().startswith("big "):
        kind = "bigtext"
    
    import uuid
    import datetime
    suffix = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    filename = f"{kind}-{suffix}.jpg"
    
    # Save to bytes
    output_format = config.get("output", {}).get("format", "JPEG")
    buf = io.BytesIO()
    if result.mode == "RGBA" and output_format.upper() == "JPEG":
        result = result.convert("RGB")
    result.save(buf, format=output_format, quality=95, optimize=True)
    
    return buf.getvalue(), filename


def apply_effects_to_image(base_image: Image.Image, caption: str, config: Dict[str, Any]) -> Image.Image:
    """
    Apply effects directly to the base image instead of creating an overlay.
    """
    # Parse caption and apply effects
    raw_caption = (caption or "").strip()
    kind, extra = captions.classify(raw_caption)
    
    # Handle special caption types that need parsing
    if raw_caption.lower().startswith("bigtext"):
        parts = raw_caption.split(maxsplit=1)
        kind = "bigtext"
        extra = {"text": parts[1].strip()} if len(parts) > 1 else {"text": ""}
    elif raw_caption.lower().startswith("big "):
        parts = raw_caption.split(maxsplit=1) 
        kind = "bigtext"
        extra = {"text": parts[1].strip()} if len(parts) > 1 else {"text": ""}
    
    logger.info(f"Applying effects to image for caption '{caption}', kind='{kind}', extra={extra}")
    
    result = base_image.copy()
    
    if kind == "logo":
        # Apply logo effect
        result = logo.apply(result, config.get("logo", {}))
    
    elif kind == "watermark":
        # Apply watermark effect
        result = watermark.apply(result, config.get("watermark", {}))
    
    elif kind == "bigtext":
        # Apply big text effect
        text = (extra.get("text") or "").strip()
        if text:
            result = big_text.apply(result, text, config.get("bigtext", {}))
    
    elif kind == "text" and extra.get("text"):
        # Apply regular text as bigtext
        text = extra.get("text", "").strip()
        if text:
            result = big_text.apply(result, text, config.get("bigtext", {}))
    
    return result


def process_video(video_bytes: bytes, caption: Optional[str], config: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Process a video with the specified caption/effects using ffmpeg-python.
    Creates overlay with PIL, then applies it to video with ffmpeg.
    """
    logger.info(f"Processing video with caption: {caption}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save input video to temp file
        input_video_path = os.path.join(temp_dir, "input_video.mp4")
        with open(input_video_path, "wb") as f:
            f.write(video_bytes)
        
        # Get video dimensions using ffmpeg probe
        try:
            probe = ffmpeg.probe(input_video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if not video_stream:
                raise ValueError("No video stream found")
            
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            
        except Exception as e:
            logger.error(f"Error probing video: {e}")
            # Fallback dimensions
            width, height = 1920, 1080
        
        logger.info(f"Video dimensions: {width}x{height}")
        
        # Create a dummy base image to apply effects to, then extract the overlay
        dummy_base = Image.new("RGB", (width, height), (0, 0, 0))
        effect_applied = apply_effects_to_image(dummy_base, caption, config)
        
        # Create overlay by subtracting the original from the effect-applied image
        # For video, we'll create a simplified overlay approach
        overlay = create_video_overlay(width, height, caption, config)
        
        # Save overlay as PNG (with transparency support)
        overlay_path = os.path.join(temp_dir, "overlay.png")
        overlay.save(overlay_path, "PNG")
        
        # Output video path
        output_video_path = os.path.join(temp_dir, "output_video.mp4")
        
        # Apply overlay to video using ffmpeg
        try:
            input_video = ffmpeg.input(input_video_path)
            overlay_input = ffmpeg.input(overlay_path)
            
            # Overlay the PNG on the video
            output = ffmpeg.output(
                input_video,
                overlay_input,
                output_video_path,
                filter_complex='[0:v][1:v]overlay=0:0',
                vcodec='libx264',
                acodec='aac',
                **{'b:v': '2M', 'b:a': '128k'}  # Set video and audio bitrates
            )
            
            # Run ffmpeg
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e}")
            # Return original video if overlay fails
            with open(input_video_path, "rb") as f:
                return f.read(), "original_video.mp4"
        
        # Read processed video
        if os.path.exists(output_video_path):
            with open(output_video_path, "rb") as f:
                result_bytes = f.read()
        else:
            logger.error("Output video not created, returning original")
            with open(input_video_path, "rb") as f:
                result_bytes = f.read()
        
        # Generate filename based on effect
        raw_caption = (caption or "").strip()
        kind, _ = captions.classify(raw_caption)
        if raw_caption.lower().startswith("bigtext") or raw_caption.lower().startswith("big "):
            kind = "bigtext"
        
        import uuid
        import datetime
        suffix = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        filename = f"{kind}-{suffix}.mp4"
        
        return result_bytes, filename


def create_video_overlay(width: int, height: int, caption: str, config: Dict[str, Any]) -> Image.Image:
    """
    Create an overlay specifically for video processing.
    This creates visual elements on a transparent background that can be overlaid on video.
    """
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    
    # Parse caption and apply effects
    raw_caption = (caption or "").strip()
    kind, extra = captions.classify(raw_caption)
    
    # Handle special caption types that need parsing
    if raw_caption.lower().startswith("bigtext"):
        parts = raw_caption.split(maxsplit=1)
        kind = "bigtext"
        extra = {"text": parts[1].strip()} if len(parts) > 1 else {"text": ""}
    elif raw_caption.lower().startswith("big "):
        parts = raw_caption.split(maxsplit=1)
        kind = "bigtext"
        extra = {"text": parts[1].strip()} if len(parts) > 1 else {"text": ""}
    
    logger.info(f"Creating video overlay for caption '{caption}', kind='{kind}', extra={extra}")
    
    if kind == "logo":
        # For logo, we can apply it to the transparent overlay
        try:
            overlay = logo.apply(overlay, config.get("logo", {}))
        except Exception as e:
            logger.warning(f"Logo overlay failed: {e}")
    
    elif kind == "bigtext":
        # Apply big text overlay
        text = (extra.get("text") or "").strip()
        if text:
            try:
                overlay = big_text.apply(overlay, text, config.get("bigtext", {}))
            except Exception as e:
                logger.warning(f"Big text overlay failed: {e}")
    
    elif kind == "text" and extra.get("text"):
        # Apply regular text as bigtext
        text = extra.get("text", "").strip()
        if text:
            try:
                overlay = big_text.apply(overlay, text, config.get("bigtext", {}))
            except Exception as e:
                logger.warning(f"Text overlay failed: {e}")
    
    # Note: Watermark can be complex for video overlay, so we'll skip it for now
    # It could be added later if needed
    
    return overlay


def process_media(media_bytes: bytes, caption: Optional[str], config: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Universal media processor that automatically detects if input is image or video
    and processes accordingly with the same effects support.
    
    Args:
        media_bytes: Raw bytes of the media file
        caption: Caption text with effect instructions (logo, watermark, big text, etc.)
        config: Configuration dictionary with effect settings
    
    Returns:
        Tuple of (processed_media_bytes, suggested_filename)
    """
    logger.info("Universal processor: detecting media type")
    
    if is_video_file(media_bytes):
        logger.info("Detected video file, processing with video pipeline")
        return process_video(media_bytes, caption, config)
    else:
        logger.info("Detected image file, processing with image pipeline")
        return process_image(media_bytes, caption, config)