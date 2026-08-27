import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredFile:
    storage_key: str
    size: int
    checksum_sha256: str


class LocalFileStorage:
    """Private local adapter; object storage can replace it through the same interface."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def save(self, organization_id: UUID, attachment_id: UUID, content: bytes) -> StoredFile:
        directory = self.root / str(organization_id)
        directory.mkdir(parents=True, exist_ok=True)
        storage_key = f"{organization_id}/{attachment_id}"
        target = (self.root / storage_key).resolve()
        if self.root not in target.parents:
            raise ValueError("Invalid storage key")
        target.write_bytes(content)
        return StoredFile(storage_key, len(content), hashlib.sha256(content).hexdigest())

    def path(self, storage_key: str) -> Path:
        target = (self.root / storage_key).resolve()
        if self.root not in target.parents or not target.is_file():
            raise FileNotFoundError(storage_key)
        return target
