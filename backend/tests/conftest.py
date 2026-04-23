from pathlib import Path

import pytest

from app.indexer import Indexer
from app.vault import VaultService


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def vault(vault_root: Path) -> VaultService:
    svc = VaultService(vault_root)
    svc.bootstrap()
    return svc


@pytest.fixture
def indexer(tmp_path: Path) -> Indexer:
    return Indexer(db_path=tmp_path / "chroma")


@pytest.fixture
def indexed_vault(vault_root: Path, indexer: Indexer) -> VaultService:
    svc = VaultService(vault_root, indexer=indexer)
    svc.bootstrap()
    indexer.reindex_all(svc.root)
    return svc
