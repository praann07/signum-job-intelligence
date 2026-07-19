from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.infrastructure.extraction.extractor import extract_from_text

router = APIRouter()


class ExtractRequest(BaseModel):
    text: str
    title: str | None = None


@router.post("/extract")
async def extract(
    body: ExtractRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    known, emerging = await extract_from_text(session, body.title or "", body.text)
    return {
        "known_skills": known,
        "emerging_candidates": emerging,
        "known_count": len(known),
        "emerging_count": len(emerging),
    }
