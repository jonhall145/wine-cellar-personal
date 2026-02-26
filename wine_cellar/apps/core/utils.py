import base64
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile


def base64_to_uploaded_file(base64_data: str, filename: str) -> InMemoryUploadedFile:
    """Convert base64 string to Django InMemoryUploadedFile.

    Args:
        base64_data: Base64-encoded image data (without data URL prefix)
        filename: Desired filename for the uploaded file

    Returns:
        InMemoryUploadedFile suitable for use with Django image fields
    """
    image_bytes = base64.b64decode(base64_data)
    image_io = BytesIO(image_bytes)

    return InMemoryUploadedFile(
        file=image_io,
        field_name=None,
        name=filename,
        content_type="image/jpeg",
        size=len(image_bytes),
        charset=None,
    )
