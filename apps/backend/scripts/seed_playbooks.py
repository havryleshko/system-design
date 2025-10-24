import json
import os
from pathlib import Path
import requests
from typing import List, Dict

from langchain_openai import OpenAIEmbeddings

BASE_DIR = Path(__file__).resolve().parent.parent / "app" / "agent" / "system_design"
JSON_PATH = BASE_DIR / "playbooks.json"


def load_playbooks() -> List[Dict[str, str]]:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return [
        {
            "topic": item["topic"].strip(),
            "title": item["title"].strip(),
            "content": item["content"].strip(),
        }
        for item in data
        if item.get("content")
    ]


def embed_contents(playbooks: List[Dict[str, str]]) -> List[Dict[str, object]]:
    model = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    embeddings = OpenAIEmbeddings(model=model)
    vectors = embeddings.embed_documents([p["content"] for p in playbooks])
    enriched = []
    for item, vector in zip(playbooks, vectors):
        enriched.append({"topic": item["topic"], "title": item["title"], "content": item["content"], "embedding": vector})
    return enriched


def upsert(playbooks: List[Dict[str, object]]) -> None:
    supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")
    table = os.getenv("KB_TABLE", "playbook_chunks")
    url = f"{supabase_url}/rest/v1/{table}"
    headers = {
        "Content-Type": "application/json",
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Prefer": "resolution=merge-duplicates",
    }
    rows = [
        {
            "topic": item["topic"],
            "title": item["title"],
            "content": item["content"],
            "embedding": item["embedding"],
        }
        for item in playbooks
    ]
    resp = requests.post(url, json=rows, headers=headers, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase upsert failed: {resp.status_code} {resp.text}")


def main() -> None:
    playbooks = load_playbooks()
    if not playbooks:
        print("No playbooks found")
        return
    enriched = embed_contents(playbooks)
    upsert(enriched)
    print(f"Seeded {len(enriched)} playbooks.")


if __name__ == "__main__":
    main()
