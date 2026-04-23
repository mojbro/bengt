from pathlib import Path

import pytest

from app.vault import VaultService


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def vault(vault_root: Path) -> VaultService:
    svc = VaultService(vault_root)
    svc.bootstrap()
    return svc
