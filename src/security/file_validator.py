"""
File upload validation and security

Provides comprehensive file validation for uploads including:
- File type validation (magic number checking)
- File size limits
- Image dimension validation
- Malicious content detection
"""

from typing import Optional, Tuple
from pathlib import Path
import magic
from PIL import Image
import io
from fastapi import UploadFile, HTTPException, status
from loguru import logger

class FileValidator:
    """Comprehensive file upload validator with security checks."""

    # Allowed MIME types with their magic number signatures
    ALLOWED_MIME_TYPES = {
        'image/jpeg': [b'\xff\xd8\xff'],
        'image/png': [b'\x89PNG\r\n\x1a\n'],
        'image/webp': [b'RIFF', b'WEBP'],
        'image/bmp': [b'BM'],
        'image/gif': [b'GIF87a', b'GIF89a']
    }

    # Maximum file sizes (in bytes)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_IMAGE_DIMENSION = 8192  # 8K pixels
    MIN_IMAGE_DIMENSION = 32  # Minimum dimension

    # Maximum pixels (to prevent decompression bombs)
    MAX_PIXELS = 100_000_000  # 100 megapixels

    @classmethod
    def validate_magic_number(cls, file_content: bytes, content_type: str) -> bool:
        """
        Validate file magic number against declared content type.

        Args:
            file_content: Raw file bytes
            content_type: Declared MIME type

        Returns:
            True if valid, False otherwise
        """
        if content_type not in cls.ALLOWED_MIME_TYPES:
            return False

        magic_numbers = cls.ALLOWED_MIME_TYPES[content_type]

        # Check if file starts with any of the valid magic numbers
        for magic_num in magic_numbers:
            if file_content.startswith(magic_num):
                return True

        # Special case for WEBP (check both RIFF and WEBP markers)
        if content_type == 'image/webp':
            return file_content.startswith(b'RIFF') and b'WEBP' in file_content[:20]

        return False

    @classmethod
    def validate_image_dimensions(cls, image: Image.Image) -> Tuple[bool, Optional[str]]:
        """
        Validate image dimensions for security.

        Args:
            image: PIL Image object

        Returns:
            Tuple of (is_valid, error_message)
        """
        width, height = image.size

        # Check minimum dimensions
        if width < cls.MIN_IMAGE_DIMENSION or height < cls.MIN_IMAGE_DIMENSION:
            return False, f"Image too small. Minimum dimensions: {cls.MIN_IMAGE_DIMENSION}x{cls.MIN_IMAGE_DIMENSION}px"

        # Check maximum dimensions
        if width > cls.MAX_IMAGE_DIMENSION or height > cls.MAX_IMAGE_DIMENSION:
            return False, f"Image too large. Maximum dimensions: {cls.MAX_IMAGE_DIMENSION}x{cls.MAX_IMAGE_DIMENSION}px"

        # Check total pixels (prevent decompression bombs)
        total_pixels = width * height
        if total_pixels > cls.MAX_PIXELS:
            return False, f"Image has too many pixels ({total_pixels:,}). Maximum: {cls.MAX_PIXELS:,}"

        return True, None

    @classmethod
    def validate_file_content(cls, file_content: bytes, content_type: str) -> Tuple[bool, Optional[str], Optional[Image.Image]]:
        """
        Validate file content comprehensively.

        Args:
            file_content: Raw file bytes
            content_type: Declared MIME type

        Returns:
            Tuple of (is_valid, error_message, image)
        """
        # Validate magic number
        if not cls.validate_magic_number(file_content, content_type):
            return False, "File type mismatch. File content doesn't match declared type.", None

        # Try to open as image
        try:
            image = Image.open(io.BytesIO(file_content))

            # Verify image can be loaded (detect corrupted files)
            image.verify()

            # Reopen for dimension checking (verify() closes the image)
            image = Image.open(io.BytesIO(file_content))

            # Validate dimensions
            is_valid, error_msg = cls.validate_image_dimensions(image)
            if not is_valid:
                return False, error_msg, None

            return True, None, image

        except Exception as e:
            logger.warning(f"Invalid image file: {e}")
            return False, f"Invalid or corrupted image file: {str(e)}", None

    @classmethod
    async def validate_upload(cls, file: UploadFile, max_size: Optional[int] = None) -> Tuple[bytes, Image.Image]:
        """
        Validate uploaded file comprehensively.

        Args:
            file: FastAPI UploadFile object
            max_size: Optional custom max file size

        Returns:
            Tuple of (file_content, image)

        Raises:
            HTTPException: If validation fails
        """
        max_size = max_size or cls.MAX_FILE_SIZE

        # Validate content type
        if not file.content_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content type not specified"
            )

        if file.content_type not in cls.ALLOWED_MIME_TYPES:
            allowed = ", ".join(cls.ALLOWED_MIME_TYPES.keys())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {allowed}"
            )

        # Read file content
        try:
            file_content = await file.read()
        except Exception as e:
            logger.error(f"Failed to read uploaded file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read uploaded file"
            )

        # Validate file size
        file_size = len(file_content)
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file uploaded"
            )

        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            current_mb = file_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({current_mb:.2f}MB). Maximum size: {max_mb:.2f}MB"
            )

        # Validate file content
        is_valid, error_msg, image = cls.validate_file_content(file_content, file.content_type)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        logger.info(f"File validated successfully: {file.filename} ({file_size:,} bytes, {image.size[0]}x{image.size[1]}px)")

        return file_content, image


# Convenience function for direct use in endpoints
async def validate_upload_file(file: UploadFile, max_size: Optional[int] = None) -> Tuple[bytes, Image.Image]:
    """
    Validate uploaded file (convenience function).

    Args:
        file: FastAPI UploadFile object
        max_size: Optional custom max file size

    Returns:
        Tuple of (file_content, image)
    """
    return await FileValidator.validate_upload(file, max_size)
