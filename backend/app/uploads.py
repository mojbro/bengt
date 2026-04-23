"""Document upload handling.

Extracts text from common document formats, asks the LLM for a short
summary + 3-5 tags, then lands two files in the vault:

  uploads/YYYY-MM-DD/<name>.<ext>   original binary (for download)
  uploads/YYYY-MM-DD/<name>.md      extracted text with frontmatter

The .md is auto-indexed by the existing VaultService hook, so semantic
search + the agent's read_file tool can reach it immediately.
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import BinaryIO

import trafilatura

from app.db.audit import AuditService
from app.llm import LLMProvider, Message, TextDelta, Usage
from app.vault import VaultService

log = logging.getLogger(__name__)


class UnsupportedFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


MAX_EXTRACTED_CHARS = 500_000  # ~500KB of text — about 100 pages of prose.

# Characters not allowed in the generated filename segment. Keep to a
# conservative POSIX-friendly subset.
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class UploadResult:
    original_path: str  # vault-relative, e.g. uploads/2026-04-23/supplier.pdf
    md_path: str  # vault-relative, e.g. uploads/2026-04-23/supplier.md
    summary: str
    tags: list[str]
    extracted_chars: int


def safe_filename(raw_name: str) -> str:
    """Strip any path components from a client-supplied filename and
    sanitise the remainder. Never returns something that would traverse
    out of the uploads folder.
    """
    # Take the final segment only; slashes in user-supplied names are
    # never desired.
    base = Path(raw_name).name
    # Replace anything outside [A-Za-z0-9._-] with underscore; collapse
    # repeats.
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    if not cleaned:
        cleaned = "file"
    # Hard cap on length to keep paths tidy.
    if len(cleaned) > 120:
        stem = cleaned[:110]
        suffix = Path(cleaned).suffix
        cleaned = stem + suffix
    return cleaned


def extract_text(filename: str, content_type: str, data: bytes) -> str:
    """Return plain text for a supported document type. Raises
    UnsupportedFileTypeError for types we don't handle yet.
    """
    suffix = Path(filename).suffix.lower()
    ct = (content_type or "").lower()

    if suffix == ".pdf" or ct == "application/pdf":
        return _extract_pdf(data)
    if suffix == ".docx" or "wordprocessingml" in ct:
        return _extract_docx(data)
    if suffix in (".md", ".markdown", ".txt") or ct.startswith("text/"):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="replace")
    if suffix in (".html", ".htm") or ct == "text/html":
        return _extract_html(data)

    raise UnsupportedFileTypeError(
        f"Can't extract text from {filename!r} (type={content_type!r}). "
        "Supported: .pdf, .docx, .txt, .md, .html."
    )


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts: list[str] = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _extract_html(data: bytes) -> str:
    try:
        html = data.decode("utf-8")
    except UnicodeDecodeError:
        html = data.decode("latin-1", errors="replace")
    return trafilatura.extract(html) or ""


_SUMMARY_PROMPT = """\
You will receive a document's plain text. Return a single JSON object with:
  "summary": a concise 2-4 sentence summary of what the document is about
  "tags": an array of 3-5 short lowercase topic tags (no spaces,
           hyphens only; e.g. "supplier", "pricing", "contract",
           "q3-review")

Respond with ONLY the JSON object. No preamble, no code fences.
"""


async def summarize_and_tag(
    text: str,
    llm: LLMProvider,
    audit: AuditService | None = None,
    conversation_id: str | None = None,
) -> tuple[str, list[str]]:
    """Ask the LLM for (summary, tags). Falls back to empty values on error."""
    # Cap input to keep the cost sane. For huge docs, the summary is based
    # on the first ~30K chars + the last ~5K (title+conclusion-ish).
    head = text[:30_000]
    tail = text[-5_000:] if len(text) > 35_000 else ""
    trimmed = head + ("\n\n[...document continues...]\n\n" + tail if tail else "")

    prompt = [
        Message(role="system", content=_SUMMARY_PROMPT),
        Message(role="user", content=trimmed),
    ]

    try:
        chunks: list[str] = []
        usage: Usage | None = None
        async for event in llm.stream(prompt, tools=None):
            if isinstance(event, TextDelta):
                chunks.append(event.text)
            elif isinstance(event, Usage):
                usage = event
    except Exception:
        log.exception("upload summarize LLM call failed")
        return "", []

    if usage and audit is not None:
        audit.record_llm_call(
            provider=llm.name,
            model=llm.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            conversation_id=conversation_id,
        )

    raw = "".join(chunks).strip()
    if raw.startswith("```"):
        # Strip fenced code if the model added it anyway.
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("summarize_and_tag: non-JSON response, ignoring: %r", raw[:200])
        return "", []

    summary = str(obj.get("summary") or "").strip()
    tags_raw = obj.get("tags") or []
    tags: list[str] = []
    if isinstance(tags_raw, list):
        for t in tags_raw:
            if isinstance(t, str):
                clean = _SAFE_FILENAME_RE.sub("-", t.strip().lower()).strip("-")
                if clean:
                    tags.append(clean)
    return summary[:800], tags[:6]


def _render_markdown(
    *,
    original_name: str,
    uploaded_at: date,
    summary: str,
    tags: list[str],
    original_vault_path: str,
    extracted_text: str,
) -> str:
    """Assemble the .md file the agent will search and the user can read."""
    lines: list[str] = ["---"]
    lines.append(f"source: {original_name}")
    lines.append(f"uploaded: {uploaded_at.isoformat()}")
    lines.append(f"original: {original_vault_path}")
    if tags:
        lines.append("tags: [" + ", ".join(tags) + "]")
    if summary:
        # Quote summary if it contains colons or quotes to stay YAML-ish.
        escaped = summary.replace("\n", " ").replace('"', '\\"')
        lines.append(f'summary: "{escaped}"')
    lines.append("---")
    lines.append("")
    if summary:
        lines.append(f"**Summary.** {summary}")
        lines.append("")
    if tags:
        lines.append("Tags: " + " ".join(f"#{t}" for t in tags))
        lines.append("")
    lines.append("## Extracted text")
    lines.append("")
    lines.append(extracted_text)
    lines.append("")
    return "\n".join(lines)


async def handle_upload(
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    vault: VaultService,
    llm: LLMProvider,
    audit: AuditService | None,
    conversation_id: str | None,
) -> UploadResult:
    """Process an uploaded file end-to-end.

    Raises UnsupportedFileTypeError for unknown types and FileTooLargeError
    if the extracted text is over the size cap.
    """
    name = safe_filename(filename)
    # Guarantee a sane suffix — user might have sent "contract" with no
    # extension, in which case we can't determine type.
    stem = Path(name).stem or "file"
    ext = Path(name).suffix.lower()
    if not ext:
        raise UnsupportedFileTypeError(
            "File has no extension; can't determine type."
        )

    extracted = extract_text(name, content_type, file_bytes).strip()
    if not extracted:
        raise UnsupportedFileTypeError(
            f"No readable text could be extracted from {name!r}."
        )
    if len(extracted) > MAX_EXTRACTED_CHARS:
        raise FileTooLargeError(
            f"Extracted text is {len(extracted):,} chars; the cap is "
            f"{MAX_EXTRACTED_CHARS:,}. Try splitting the document."
        )

    today = date.today()
    dir_path = f"uploads/{today.isoformat()}"
    original_vault_path = f"{dir_path}/{name}"
    md_vault_path = f"{dir_path}/{stem}.md"

    # Write the original binary first — even if summarisation fails later,
    # the user still has the file they uploaded.
    vault.write_bytes(original_vault_path, file_bytes, actor="user")

    summary, tags = await summarize_and_tag(
        extracted, llm, audit=audit, conversation_id=conversation_id
    )

    md = _render_markdown(
        original_name=name,
        uploaded_at=today,
        summary=summary,
        tags=tags,
        original_vault_path=original_vault_path,
        extracted_text=extracted,
    )
    vault.write(md_vault_path, md, actor="user")

    return UploadResult(
        original_path=original_vault_path,
        md_path=md_vault_path,
        summary=summary,
        tags=tags,
        extracted_chars=len(extracted),
    )


def open_vault_file_for_stream(
    vault: VaultService, path: str
) -> tuple[BinaryIO, int, str]:
    """Open a vault file for binary streaming. Returns (handle, size, filename)."""
    from app.vault.paths import safe_resolve

    target = safe_resolve(vault.root, path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(path)
    size = target.stat().st_size
    return target.open("rb"), size, target.name
