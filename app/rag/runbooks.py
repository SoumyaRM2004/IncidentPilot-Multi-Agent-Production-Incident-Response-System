import os
import re
from typing import List, Dict, Any

RUNBOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "runbooks")


def load_and_chunk_runbooks(runbooks_dir: str = RUNBOOKS_DIR) -> List[Dict[str, Any]]:
    """Loads markdown runbooks and splits them by section headers with metadata."""
    chunks = []
    chunk_index = 1

    if not os.path.exists(runbooks_dir):
        return chunks

    for filename in os.listdir(runbooks_dir):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(runbooks_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract title from # Header
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        doc_title = title_match.group(1).strip() if title_match else filename

        # Split into sections by ## Header
        sections = re.split(r"(?=^##\s+)", content, flags=re.MULTILINE)

        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue

            sec_title_match = re.search(r"^##\s+(.+)$", sec, re.MULTILINE)
            sec_title = sec_title_match.group(1).strip() if sec_title_match else "Overview"

            # Clean header line from text content
            body = re.sub(r"^##\s+.+$", "", sec, flags=re.MULTILINE).strip()
            if not body:
                body = sec

            chunks.append({
                "chunk_id": f"RUNBOOK-{chunk_index:02d}",
                "source": filename,
                "title": doc_title,
                "section": sec_title,
                "content": f"{doc_title} - {sec_title}\n{body}"
            })
            chunk_index += 1

    return chunks
