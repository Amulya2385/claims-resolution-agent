"""Split policy documents on structure (## headings), not a fixed
character count — same design as Project 1's chunker."""
import glob
import os
import re


def chunk_file(path: str) -> list[dict]:
    text = open(path, encoding="utf-8").read()
    doc_id = os.path.splitext(os.path.basename(path))[0]
    parts = re.split(r"\n(?=## )", text)
    chunks = []
    title_line = parts[0].strip().splitlines()[0].lstrip("# ").strip()
    for part in parts:
        lines = part.strip().splitlines()
        if not lines:
            continue
        heading = lines[0].lstrip("# ").strip() if lines[0].startswith("#") else title_line
        body = "\n".join(lines[1:]).strip() if lines[0].startswith("#") else part.strip()
        if not body:
            continue
        locator = f"{doc_id}#{heading}"
        chunks.append({"doc_id": doc_id, "locator": locator, "heading": heading, "text": body})
    return chunks


def chunk_corpus(directory: str) -> list[dict]:
    all_chunks = []
    for path in sorted(glob.glob(os.path.join(directory, "*.md"))):
        all_chunks.extend(chunk_file(path))
    return all_chunks
