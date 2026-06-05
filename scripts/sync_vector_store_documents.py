#!/usr/bin/env python3
"""Sync local RAG markdown files into an Azure/OpenAI vector store."""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"


@dataclass(frozen=True)
class RemoteDocument:
    file_id: str
    filename: str
    source_sha256: str | None
    created_at: int | None


def parse_args() -> argparse.Namespace:
    load_dotenv(ENV_PATH)

    parser = argparse.ArgumentParser(
        description="Upload local RAG documents to a vector store without duplicating filenames.",
    )
    parser.add_argument(
        "--vector-store-id",
        default=os.getenv("VECTOR_STORE_ID", "").strip(),
        help="Vector store ID. Defaults to VECTOR_STORE_ID from .env.",
    )
    parser.add_argument(
        "--documents-glob",
        default=os.getenv("DOCUMENTS_GLOB", "work/documents/*.md"),
        help="Glob for local documents. Defaults to DOCUMENTS_GLOB from .env.",
    )
    parser.add_argument(
        "--replace-changed",
        action="store_true",
        help="Replace a remote file when the same filename exists but its stored hash differs.",
    )
    parser.add_argument(
        "--prune-duplicates",
        action="store_true",
        help="Delete duplicate remote files with the same filename, keeping the newest one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned changes without uploading or deleting files.",
    )
    return parser.parse_args()


def get_openai_client() -> Any:
    load_dotenv(ENV_PATH)
    project_endpoint = os.environ["PROJECT_ENDPOINT"]
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )
    return project_client.get_openai_client()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_document_paths(documents_glob: str) -> list[Path]:
    paths = [Path(path) for path in sorted(glob.glob(documents_glob))]
    return [path for path in paths if path.is_file()]


def vector_store_documents(openai_client: Any, vector_store_id: str) -> dict[str, list[RemoteDocument]]:
    documents: dict[str, list[RemoteDocument]] = {}

    for vector_file in openai_client.vector_stores.files.list(vector_store_id=vector_store_id, limit=100):
        file = openai_client.files.retrieve(vector_file.id)
        attributes = getattr(vector_file, "attributes", None) or {}
        filename = getattr(file, "filename", vector_file.id)
        remote_document = RemoteDocument(
            file_id=vector_file.id,
            filename=filename,
            source_sha256=attributes.get("source_sha256"),
            created_at=getattr(vector_file, "created_at", None),
        )
        documents.setdefault(filename, []).append(remote_document)

    for entries in documents.values():
        entries.sort(key=lambda item: item.created_at or 0, reverse=True)

    return documents


def delete_vector_store_file(openai_client: Any, vector_store_id: str, file_id: str, dry_run: bool) -> None:
    if dry_run:
        print(f"Would delete duplicate/stale remote file {file_id}")
        return

    openai_client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
    openai_client.files.delete(file_id)
    print(f"Deleted remote file {file_id}")


def upload_document(openai_client: Any, vector_store_id: str, path: Path, source_sha256: str, dry_run: bool) -> None:
    if dry_run:
        print(f"Would upload {path}")
        return

    with path.open("rb") as document:
        file = openai_client.vector_stores.files.upload_and_poll(
            vector_store_id=vector_store_id,
            file=document,
            attributes={
                "source_filename": path.name,
                "source_path": path.as_posix(),
                "source_sha256": source_sha256,
            },
        )
    print(f"Uploaded {path} as {file.id}")


def sync_documents(
    openai_client: Any,
    vector_store_id: str,
    documents_glob: str,
    replace_changed: bool,
    prune_duplicates: bool,
    dry_run: bool,
) -> None:
    local_paths = local_document_paths(documents_glob)
    if not local_paths:
        raise SystemExit(f"No documents matched {documents_glob}")

    remote_by_filename = vector_store_documents(openai_client, vector_store_id)
    uploaded = 0
    skipped = 0
    replaced = 0

    for path in local_paths:
        source_sha256 = file_sha256(path)
        remote_entries = remote_by_filename.get(path.name, [])

        if prune_duplicates and len(remote_entries) > 1:
            for duplicate in remote_entries[1:]:
                delete_vector_store_file(openai_client, vector_store_id, duplicate.file_id, dry_run)
            remote_entries = remote_entries[:1]

        if not remote_entries:
            upload_document(openai_client, vector_store_id, path, source_sha256, dry_run)
            uploaded += 1
            continue

        current = remote_entries[0]
        if current.source_sha256 and current.source_sha256 != source_sha256:
            if replace_changed:
                delete_vector_store_file(openai_client, vector_store_id, current.file_id, dry_run)
                upload_document(openai_client, vector_store_id, path, source_sha256, dry_run)
                replaced += 1
            else:
                print(f"Changed locally but not replaced: {path} (run with --replace-changed)")
                skipped += 1
            continue

        print(f"Skipped existing document: {path.name}")
        skipped += 1

    print(f"Sync complete: uploaded={uploaded}, replaced={replaced}, skipped={skipped}")


def main() -> None:
    args = parse_args()
    if not args.vector_store_id:
        raise SystemExit("VECTOR_STORE_ID is required. Set it in .env or pass --vector-store-id.")

    openai_client = get_openai_client()
    sync_documents(
        openai_client=openai_client,
        vector_store_id=args.vector_store_id,
        documents_glob=args.documents_glob,
        replace_changed=args.replace_changed,
        prune_duplicates=args.prune_duplicates,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
