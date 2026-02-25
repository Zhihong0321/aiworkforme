"""
Public short-lived media routes for one-time media fetch (e.g., voice notes).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.app.runtime.temp_media_store import consume_temp_media

router = APIRouter(prefix="/api/v1/public", tags=["Public Media"])


@router.get("/temp-media/{token}")
def get_temp_media(token: str):
    try:
        body, mime_type, file_name = consume_temp_media(token)
    except KeyError:
        raise HTTPException(status_code=404, detail="Temp media not found or expired")

    return Response(
        content=body,
        media_type=mime_type,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Content-Disposition": f'inline; filename="{file_name}"',
        },
    )

