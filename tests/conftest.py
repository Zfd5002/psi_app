from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base


@pytest.fixture
def mkdb():
    def _mkdb():
        eng = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=eng)
        ensure_schema(engine_override=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        return eng, SessionTmp

    return _mkdb


@pytest.fixture
def dummy_templates():
    class _DummyTemplates:
        @staticmethod
        def TemplateResponse(_name: str, ctx: dict):
            return SimpleNamespace(context=ctx)

    return _DummyTemplates()


@pytest.fixture
def mk_query_request():
    def _mk_request(query: dict[str, str]):
        return SimpleNamespace(query_params=query)

    return _mk_request
