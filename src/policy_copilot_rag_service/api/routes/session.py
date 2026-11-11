"""Persistent query sessions with a selected library."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..db import repository as repo
from ..db.models import ChatSession
from ..db.session import get_db
from ..schemas import SessionCreate, SessionList, SessionOut, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _get_session(db: Session, session_id: int) -> ChatSession:
    session = repo.get_chat_session_by_id(db, session_id)
    if session is None:
        raise HTTPException(404, f"Session with ID: {session_id} Not Found")
    return session


def _require_library(db: Session, library_id: int) -> None:
    if repo.get_library_by_id(db, library_id) is None:
        raise HTTPException(404, f"Library with ID: {library_id} Not Found")


@router.post("", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    _require_library(db, body.library_id)
    session = repo.add_chat_session(db, library_id=body.library_id)
    db.commit()
    return session


@router.get("", response_model=SessionList)
def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total, sessions = repo.get_chat_sessions_list(db, limit, offset)
    return SessionList(total=total, items=[SessionOut.model_validate(session) for session in sessions])


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)):
    return _get_session(db, session_id)


@router.patch("/{session_id}", response_model=SessionOut)
def select_library(session_id: int, body: SessionUpdate, db: Session = Depends(get_db)):
    session = _get_session(db, session_id)
    _require_library(db, body.library_id)
    session.library_id = body.library_id
    db.commit()
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = _get_session(db, session_id)
    repo.delete_chat_session(db, session)
    db.commit()
    return Response(status_code=204)
