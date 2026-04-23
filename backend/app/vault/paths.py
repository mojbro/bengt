from pathlib import Path


class PathSafetyError(ValueError):
    """Raised when a user-supplied path would escape the vault root."""


def safe_resolve(vault_root: Path, user_path: str) -> Path:
    """Resolve ``user_path`` relative to ``vault_root``, rejecting traversal.

    Rejects absolute paths and any path that resolves outside ``vault_root``,
    including escapes via ``..`` and symlinks.
    """
    root = vault_root.resolve()
    if user_path == "":
        return root

    candidate = Path(user_path)
    if candidate.is_absolute():
        raise PathSafetyError(f"absolute paths are not allowed: {user_path!r}")

    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise PathSafetyError(f"path escapes the vault: {user_path!r}") from e
    return resolved
