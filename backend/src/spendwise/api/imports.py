"""Upload a statement, list past imports, undo one."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from sqlmodel import Session, delete, select

from ..config import get_settings
from ..db import get_session
from ..models import ImportBatch, ImportDuplicate, Transaction, User
from ..services.imports import DuplicateRace, import_statement
from .deps import MeteredAI, get_current_user, optional_ai
from .schemas import ImportOut

router = APIRouter(prefix="/api/imports", tags=["imports"])
MAX_ID = 2**31 - 1


@router.post("", response_model=ImportOut, status_code=status.HTTP_201_CREATED)
def upload(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    ai: MeteredAI | None = Depends(optional_ai),
):
    # a plain `def`: FastAPI runs it in a worker thread, so parsing a big file (or waiting for the AI)
    # never freezes the server for everyone else, as an `async def` here would
    s = get_settings()
    limit = int(s.max_upload_mb * 1024 * 1024)
    if int(request.headers.get("content-length") or 0) > limit + 64 * 1024:  # refuse before reading
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Files up to {s.max_upload_mb:g} MB, please.")
    data = file.file.read(limit + 1)  # never read more than the limit into memory
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Files up to {s.max_upload_mb:g} MB, please.")
    if not data:
        raise HTTPException(400, "The file is empty.")
    name = (file.filename or "statement.csv").replace("\\", "/").split("/")[-1]
    try:
        batch, skipped, by_source = import_statement(session, user, data, name, ai, s.max_import_rows)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except DuplicateRace:
        raise HTTPException(409, "Another import of these payments just ran. Try again.") from None
    return ImportOut(**batch.model_dump(), skipped_rows=skipped[:50], categorized_by=by_source)


@router.get("", response_model=list[ImportOut])
def history(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(
        select(ImportBatch).where(ImportBatch.user_id == user.id).order_by(ImportBatch.created_at.desc())
    ).all()
    return [ImportOut(**b.model_dump()) for b in rows]


@router.get("/sample")
def sample_statement(user: User = Depends(get_current_user)):
    """The made-up practice statement, so anyone can try an import without their own bank file."""
    path = Path(__file__).resolve().parents[3] / "data" / "sample_statement.csv"
    return FileResponse(path, media_type="text/csv", filename="sample_statement.csv")


@router.delete("/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
def undo(
    import_id: int = PathParam(ge=1, le=MAX_ID),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Removes the import and the payments only it brought in. A payment that a later import also
    contained is handed over to that import instead of being deleted."""
    batch = session.get(ImportBatch, import_id)
    if batch is None or batch.user_id != user.id:
        raise HTTPException(404, "No such import.")
    rows = session.exec(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.import_id == batch.id)
    ).all()
    keys = [t.dedup_key for t in rows]
    heirs: dict[str, ImportDuplicate] = {}  # dedup key -> the earliest other import that also had it
    for i in range(0, len(keys), 500):  # one query per 500 payments, not one per payment
        for d in session.exec(
            select(ImportDuplicate)
            .where(
                ImportDuplicate.user_id == user.id,
                ImportDuplicate.import_id != batch.id,
                ImportDuplicate.dedup_key.in_(keys[i : i + 500]),
            )
            .order_by(ImportDuplicate.import_id)
        ).all():
            heirs.setdefault(d.dedup_key, d)
    for t in rows:
        heir = heirs.get(t.dedup_key)
        if heir:
            t.import_id = heir.import_id
            session.add(t)
            session.delete(heir)
        else:
            session.delete(t)
    session.exec(delete(ImportDuplicate).where(ImportDuplicate.import_id == batch.id))
    session.delete(batch)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
