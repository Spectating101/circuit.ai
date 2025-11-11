"""
Mobile-Optimized API Endpoints

Features:
- Image optimization and compression
- Reduced payloads
- Pagination
- Caching headers
- Progressive image loading
- Offline support
- Push notifications
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, File, UploadFile, Query, Header, Response, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from PIL import Image
import io
from loguru import logger
from datetime import datetime, timedelta
import hashlib
import json


router = APIRouter(prefix="/api/mobile/v1", tags=["Mobile"])


class MobileAnalysisRequest(BaseModel):
    """Mobile analysis request with compression options."""
    quality: int = Field(default=80, ge=1, le=100, description="Image quality (1-100)")
    max_dimension: int = Field(default=2048, description="Max image dimension in pixels")
    thumbnail_size: int = Field(default=512, description="Thumbnail size")


class MobileAnalysisResponse(BaseModel):
    """Mobile-optimized analysis response."""
    id: str
    status: str
    progress: int = Field(ge=0, le=100)
    thumbnail_url: Optional[str]
    component_count: int
    estimated_time_remaining: Optional[int]  # seconds

    # Minimal data for quick display
    quick_stats: Dict[str, Any]

    # Full data URL (fetch separately if needed)
    full_data_url: Optional[str]


class ComponentSummary(BaseModel):
    """Lightweight component summary for mobile."""
    id: str
    type: str
    confidence: float
    x: int
    y: int


class MobileBOMItem(BaseModel):
    """Lightweight BOM item."""
    part_number: str
    quantity: int
    unit_price: float
    total_price: float


@router.post("/analyze")
async def mobile_analyze(
    file: UploadFile = File(...),
    quality: int = Query(default=80, ge=1, le=100),
    max_dimension: int = Query(default=2048)
) -> MobileAnalysisResponse:
    """
    Mobile-optimized PCB analysis endpoint.

    Automatically compresses images and returns optimized payload.

    Args:
        file: PCB image file
        quality: JPEG quality (1-100)
        max_dimension: Maximum dimension for image

    Returns:
        Mobile-optimized analysis response
    """
    # Read and optimize image
    image_data = await file.read()
    optimized_image = await optimize_image_for_mobile(
        image_data,
        max_dimension=max_dimension,
        quality=quality
    )

    # Create thumbnail
    thumbnail = await create_thumbnail(image_data, size=512)

    # Start analysis (async)
    analysis_id = "analysis_" + hashlib.md5(image_data).hexdigest()[:16]

    # Store optimized image and thumbnail
    # TODO: Upload to CDN/storage

    return MobileAnalysisResponse(
        id=analysis_id,
        status="processing",
        progress=0,
        thumbnail_url=f"/api/mobile/v1/thumbnails/{analysis_id}",
        component_count=0,
        estimated_time_remaining=5,
        quick_stats={
            "file_size_original": len(image_data),
            "file_size_optimized": len(optimized_image),
            "compression_ratio": f"{(1 - len(optimized_image)/len(image_data))*100:.1f}%"
        },
        full_data_url=f"/api/mobile/v1/analysis/{analysis_id}/full"
    )


@router.get("/analysis/{analysis_id}")
async def get_mobile_analysis(
    analysis_id: str,
    if_none_match: Optional[str] = Header(None)
) -> Response:
    """
    Get mobile-optimized analysis results.

    Supports ETags for caching.

    Args:
        analysis_id: Analysis ID
        if_none_match: ETag from previous request

    Returns:
        Mobile analysis response with caching headers
    """
    # Get analysis data
    # TODO: Fetch from database
    analysis_data = {
        "id": analysis_id,
        "status": "completed",
        "progress": 100,
        "component_count": 145,
        "quick_stats": {
            "resistors": 45,
            "capacitors": 38,
            "ics": 12,
            "total_cost": 24.50
        }
    }

    # Generate ETag
    etag = hashlib.md5(json.dumps(analysis_data).encode()).hexdigest()

    # Check if client has cached version
    if if_none_match == etag:
        return Response(status_code=304)  # Not Modified

    # Return with caching headers
    return Response(
        content=json.dumps(analysis_data),
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "Last-Modified": datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        }
    )


@router.get("/analysis/{analysis_id}/components")
async def get_mobile_components(
    analysis_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    type_filter: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """
    Get paginated component list (mobile-optimized).

    Args:
        analysis_id: Analysis ID
        page: Page number
        page_size: Items per page
        type_filter: Filter by component type

    Returns:
        Paginated component list
    """
    # TODO: Fetch from database with pagination

    # Mock data
    components = [
        ComponentSummary(
            id=f"comp_{i}",
            type="resistor",
            confidence=0.95,
            x=100 + i*10,
            y=200
        )
        for i in range(20)
    ]

    return {
        "page": page,
        "page_size": page_size,
        "total_pages": 8,
        "total_items": 145,
        "components": [c.dict() for c in components],
        "has_next": page < 8,
        "next_page_url": f"/api/mobile/v1/analysis/{analysis_id}/components?page={page+1}" if page < 8 else None
    }


@router.get("/analysis/{analysis_id}/bom")
async def get_mobile_bom(
    analysis_id: str,
    format: str = Query(default="summary", regex="^(summary|detailed)$")
) -> Dict[str, Any]:
    """
    Get BOM (mobile-optimized).

    Args:
        analysis_id: Analysis ID
        format: Response format (summary or detailed)

    Returns:
        BOM data
    """
    if format == "summary":
        # Lightweight summary
        return {
            "total_items": 45,
            "total_cost": 24.50,
            "top_items": [
                {
                    "part_number": "RC0603FR-0710KL",
                    "quantity": 20,
                    "total": 0.20
                }
            ],
            "download_url": f"/api/mobile/v1/analysis/{analysis_id}/bom/download"
        }
    else:
        # Full BOM
        return {
            "items": [],  # Full list
            "total_cost": 24.50,
            "currency": "USD"
        }


@router.get("/thumbnails/{analysis_id}")
async def get_thumbnail(
    analysis_id: str,
    size: int = Query(default=512, ge=64, le=1024)
) -> StreamingResponse:
    """
    Get thumbnail image.

    Args:
        analysis_id: Analysis ID
        size: Thumbnail size

    Returns:
        Thumbnail image
    """
    # TODO: Fetch from storage

    # Create placeholder thumbnail
    img = Image.new('RGB', (size, size), color='gray')

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85, optimize=True)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            "Content-Disposition": f"inline; filename=thumbnail_{analysis_id}.jpg"
        }
    )


@router.get("/images/{analysis_id}")
async def get_optimized_image(
    analysis_id: str,
    quality: int = Query(default=80, ge=1, le=100),
    width: Optional[int] = Query(default=None, ge=100, le=4096)
) -> StreamingResponse:
    """
    Get optimized PCB image.

    Supports responsive sizing for different screen sizes.

    Args:
        analysis_id: Analysis ID
        quality: JPEG quality
        width: Desired width (maintains aspect ratio)

    Returns:
        Optimized image
    """
    # TODO: Fetch original image from storage

    # Create placeholder
    img = Image.new('RGB', (2048, 2048), color='blue')

    # Resize if width specified
    if width:
        aspect_ratio = img.height / img.width
        height = int(width * aspect_ratio)
        img = img.resize((width, height), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Vary": "Accept-Encoding"
        }
    )


@router.post("/push/register")
async def register_push_token(
    user_id: str,
    token: str,
    platform: str = Query(regex="^(ios|android|web)$")
) -> Dict[str, str]:
    """
    Register push notification token.

    Args:
        user_id: User ID
        token: Device token
        platform: Platform (ios/android/web)

    Returns:
        Success message
    """
    # TODO: Store token in database

    logger.info(f"Registered push token for user {user_id} on {platform}")

    return {
        "status": "success",
        "message": "Push notifications enabled"
    }


@router.get("/offline/manifest")
async def get_offline_manifest() -> Dict[str, Any]:
    """
    Get offline manifest for PWA.

    Returns:
        Manifest with cacheable resources
    """
    return {
        "name": "Circuit.AI",
        "short_name": "Circuit.AI",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#3498db",
        "icons": [
            {
                "src": "/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ],
        "offline_urls": [
            "/",
            "/api/mobile/v1/analysis/recent",
            "/static/css/mobile.css",
            "/static/js/mobile.js"
        ]
    }


@router.get("/analysis/recent")
async def get_recent_analyses(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get recent analyses (optimized for mobile).

    Args:
        user_id: User ID
        limit: Number of results

    Returns:
        Recent analyses
    """
    # TODO: Fetch from database

    return {
        "analyses": [
            {
                "id": f"analysis_{i}",
                "pcb_name": f"Board {i}",
                "thumbnail_url": f"/api/mobile/v1/thumbnails/analysis_{i}",
                "component_count": 100 + i * 10,
                "created_at": (datetime.utcnow() - timedelta(days=i)).isoformat(),
                "status": "completed"
            }
            for i in range(limit)
        ],
        "total": limit,
        "has_more": False
    }


async def optimize_image_for_mobile(
    image_data: bytes,
    max_dimension: int = 2048,
    quality: int = 80
) -> bytes:
    """
    Optimize image for mobile display.

    Args:
        image_data: Original image bytes
        max_dimension: Maximum width/height
        quality: JPEG quality

    Returns:
        Optimized image bytes
    """
    img = Image.open(io.BytesIO(image_data))

    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    # Resize if too large
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    # Save optimized
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)

    return buffer.getvalue()


async def create_thumbnail(
    image_data: bytes,
    size: int = 512
) -> bytes:
    """
    Create thumbnail from image.

    Args:
        image_data: Original image bytes
        size: Thumbnail size

    Returns:
        Thumbnail bytes
    """
    img = Image.open(io.BytesIO(image_data))

    # Convert to RGB
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    # Create square thumbnail with center crop
    img.thumbnail((size, size), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85, optimize=True)

    return buffer.getvalue()
