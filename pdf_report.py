#!/usr/bin/env python3
"""Convert a Markdown digest into a simple, dependency-free PDF."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import List


LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MARKUP_RE = re.compile(r"[*_`#]")


def markdown_lines(markdown: str) -> List[str]:
    result = []
    for line in markdown.splitlines():
        line = LINK_RE.sub(r"\1 (\2)", line)
        line = MARKUP_RE.sub("", line).strip()
        if not line:
            result.append("")
            continue
        result.extend(textwrap.wrap(line, width=95, break_long_words=False))
    return result


def pdf_escape(value: str) -> bytes:
    encoded = value.encode("cp1252", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def page_stream(lines: List[str]) -> bytes:
    commands = [b"BT", b"/F1 10 Tf", b"50 790 Td", b"14 TL"]
    for line in lines:
        commands.append(b"(" + pdf_escape(line) + b") Tj")
        commands.append(b"T*")
    commands.append(b"ET")
    return b"\n".join(commands)


def write_pdf(markdown_path: Path, pdf_path: Path) -> None:
    lines = markdown_lines(markdown_path.read_text(encoding="utf-8"))
    pages = [lines[index : index + 52] for index in range(0, len(lines), 52)] or [[]]

    objects = [b"", b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    page_ids = []
    for page in pages:
        page_id = len(objects)
        stream_id = page_id + 1
        page_ids.append(page_id)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode()
        )
        stream = page_stream(page)
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, body in enumerate(objects[1:], 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(output)
