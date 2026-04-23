from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from git import Actor, Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError

from app.indexer import Indexer
from app.vault.paths import safe_resolve

ActorName = Literal["user", "agent", "system"]

_ACTORS: dict[str, Actor] = {
    "user": Actor("user", "user@localhost"),
    "agent": Actor("agent", "agent@localhost"),
    "system": Actor("system", "system@localhost"),
}

_STUB_FILES: dict[str, str] = {
    "todos.md": "# Todos\n",
    "memory.md": "# Memory\n",
    "preferences.md": "# Preferences\n",
}


class VaultError(Exception):
    """Base class for vault errors."""


class NotFoundError(VaultError):
    """Requested path does not exist in the vault."""


class EditError(VaultError):
    """Edit preconditions not met (target string missing or not unique)."""


@dataclass(frozen=True)
class VaultEntry:
    path: str
    is_dir: bool
    size: int | None


class VaultService:
    def __init__(self, root: Path, indexer: Indexer | None = None):
        self.root = Path(root)
        self.indexer = indexer

    def bootstrap(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        repo = self._ensure_repo()
        for name, content in _STUB_FILES.items():
            path = self.root / name
            if path.exists():
                continue
            path.write_text(content)
            repo.index.add([name])
            repo.index.commit(
                f"system: initialize {name}",
                author=_ACTORS["system"],
                committer=_ACTORS["system"],
            )

    def list(self, path: str = "") -> list[VaultEntry]:
        target = safe_resolve(self.root, path)
        if not target.exists():
            raise NotFoundError(path)
        if not target.is_dir():
            raise VaultError(f"not a directory: {path}")
        root = self.root.resolve()
        entries: list[VaultEntry] = []
        for child in sorted(target.iterdir()):
            if child.name == ".git":
                continue
            rel = child.relative_to(root).as_posix()
            entries.append(
                VaultEntry(
                    path=rel,
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else None,
                )
            )
        return entries

    def read(self, path: str) -> str:
        target = safe_resolve(self.root, path)
        if not target.exists() or not target.is_file():
            raise NotFoundError(path)
        return target.read_text()

    def write(self, path: str, content: str, actor: ActorName = "user") -> None:
        target = safe_resolve(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self._commit(target, "write", actor)

    def edit(
        self,
        path: str,
        old_string: str,
        new_string: str,
        actor: ActorName = "user",
    ) -> None:
        target = safe_resolve(self.root, path)
        if not target.exists() or not target.is_file():
            raise NotFoundError(path)
        content = target.read_text()
        count = content.count(old_string)
        if count == 0:
            raise EditError(f"old_string not found in {path}")
        if count > 1:
            raise EditError(
                f"old_string matches {count} times in {path}; provide more context"
            )
        target.write_text(content.replace(old_string, new_string, 1))
        self._commit(target, "edit", actor)

    def append(self, path: str, content: str, actor: ActorName = "user") -> None:
        target = safe_resolve(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as f:
            f.write(content)
        self._commit(target, "append", actor)

    def _ensure_repo(self) -> Repo:
        try:
            return Repo(self.root)
        except (InvalidGitRepositoryError, NoSuchPathError):
            return Repo.init(self.root, initial_branch="main")

    def _commit(self, target: Path, op: str, actor: ActorName) -> None:
        repo = self._ensure_repo()
        rel = target.relative_to(self.root.resolve()).as_posix()
        repo.index.add([rel])
        author = _ACTORS[actor]
        repo.index.commit(
            f"{actor}: {op} {rel}",
            author=author,
            committer=author,
        )
        if self.indexer and target.suffix == ".md":
            self.indexer.upsert(rel, target.read_text())
