"""
Public media routes for ephemeral and managed outbound files.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from src.app.runtime.sales_materials import get_sales_material_by_public_token, sales_material_path
from src.app.runtime.temp_media_store import consume_temp_media
from src.infra.database import get_session

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


@router.get("/sales-materials/{public_token}")
def get_sales_material(public_token: str, session: Session = Depends(get_session)):
    material = get_sales_material_by_public_token(session, public_token)
    if not material:
        raise HTTPException(status_code=404, detail="Sales material not found")

    file_path = sales_material_path(material)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Sales material file is missing")

    return Response(
        content=file_path.read_bytes(),
        media_type=material.media_type or "application/octet-stream",
        headers={
            "Cache-Control": "public, max-age=300",
            "Content-Disposition": f'inline; filename="{material.filename}"',
        },
    )
