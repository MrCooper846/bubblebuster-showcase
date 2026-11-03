from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath

from packages.ingestion.object_store import (
    ObjectCollisionError,
    ObjectIntegrityError,
    ObjectNotFoundError,
    ObjectStoreError,
    StoredObject,
    StoredObjectRef,
    content_addressed_key,
    digest,
)


class LocalObjectStore:
    provider = "LOCAL"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.bucket_name = str(self.root)

    def put(
        self,
        content: bytes,
        *,
        key: str | None = None,
        content_type: str | None = None,
    ) -> StoredObject:
        object_hash = digest(content)
        object_key = self._normalise_key(key or content_addressed_key(object_hash))
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self._verify_existing(path, content, object_hash, object_key)
        else:
            self._write_once(path, content, object_hash, object_key)
        return StoredObject(
            provider=self.provider,
            bucket_name=self.bucket_name,
            object_key=object_key,
            sha256=object_hash,
            byte_size=len(content),
            content_type=content_type,
        )

    def get(self, object_ref: StoredObjectRef, *, verify: bool = True) -> bytes:
        self._validate_ref(object_ref)
        path = self._path(self._normalise_key(object_ref.object_key))
        try:
            content = path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(f"object not found: {object_ref.object_key}") from exc
        except OSError as exc:
            raise ObjectStoreError(f"failed to read object: {object_ref.object_key}") from exc
        if verify and digest(content) != object_ref.sha256:
            raise ObjectIntegrityError(f"digest mismatch for object: {object_ref.object_key}")
        return content

    def exists(self, sha256: str) -> bool:
        return self._path(content_addressed_key(sha256)).is_file()

    def path_for(self, object_ref: StoredObjectRef) -> Path:
        """Resolve a local reference for diagnostics and integrity jobs."""
        self._validate_ref(object_ref)
        return self._path(self._normalise_key(object_ref.object_key))

    def _write_once(self, path: Path, content: bytes, object_hash: str, object_key: str) -> None:
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=".archive-", delete=False
            ) as file:
                temporary_name = file.name
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            try:
                os.link(temporary_name, path)
            except FileExistsError:
                self._verify_existing(path, content, object_hash, object_key)
        except ObjectStoreError:
            raise
        except OSError as exc:
            raise ObjectStoreError(f"failed to store object: {object_key}") from exc
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    @staticmethod
    def _verify_existing(path: Path, content: bytes, object_hash: str, object_key: str) -> None:
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise ObjectStoreError(f"failed to inspect existing object: {object_key}") from exc
        if existing != content:
            if digest(existing) != object_hash:
                raise ObjectCollisionError(
                    f"immutable key already contains different bytes: {object_key}"
                )
            raise ObjectIntegrityError(f"stored object is inconsistent: {object_key}")

    def _validate_ref(self, object_ref: StoredObjectRef) -> None:
        if object_ref.provider != self.provider or object_ref.bucket_name != self.bucket_name:
            raise ObjectStoreError("object reference belongs to a different storage backend")

    @staticmethod
    def _normalise_key(key: str) -> str:
        candidate = PurePosixPath(key)
        if (
            candidate.is_absolute()
            or not candidate.parts
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise ObjectStoreError("object key must be a safe relative POSIX path")
        return candidate.as_posix()

    def _path(self, key: str) -> Path:
        return self.root.joinpath(*PurePosixPath(key).parts)
