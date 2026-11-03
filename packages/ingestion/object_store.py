from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256 as calculate_sha256
from typing import Protocol, runtime_checkable


class ObjectStoreError(RuntimeError):
    """Base error for provider-independent object storage failures."""


class ObjectNotFoundError(ObjectStoreError):
    """The referenced object does not exist."""


class ObjectIntegrityError(ObjectStoreError):
    """Stored bytes do not match their expected digest."""


class ObjectCollisionError(ObjectStoreError):
    """An immutable key already contains different bytes."""


@dataclass(frozen=True, slots=True)
class StoredObjectRef:
    provider: str
    bucket_name: str
    object_key: str
    sha256: str


@dataclass(frozen=True, slots=True)
class StoredObject(StoredObjectRef):
    byte_size: int
    content_type: str | None = None

    @property
    def ref(self) -> StoredObjectRef:
        return StoredObjectRef(
            provider=self.provider,
            bucket_name=self.bucket_name,
            object_key=self.object_key,
            sha256=self.sha256,
        )


def digest(content: bytes) -> str:
    return calculate_sha256(content).hexdigest()


def content_addressed_key(sha256: str) -> str:
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("sha256 must be a lowercase hexadecimal digest")
    return f"sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}"


@runtime_checkable
class ObjectStore(Protocol):
    provider: str
    bucket_name: str

    def put(
        self,
        content: bytes,
        *,
        key: str | None = None,
        content_type: str | None = None,
    ) -> StoredObject: ...

    def get(self, object_ref: StoredObjectRef, *, verify: bool = True) -> bytes: ...

    def exists(self, sha256: str) -> bool: ...
