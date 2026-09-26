import hashlib
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger


class EvidenceStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.evidence_path
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def store_file(
        self,
        data: bytes,
        filename_prefix: str,
        extension: str = ".png",
    ) -> tuple[str, str]:
        """
        Stores binary evidence data to filesystem with content hashing.
        Returns: (storage_reference, content_hash)
        """
        content_hash = self.calculate_sha256(data)
        safe_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ("-", "_"))
        filename = f"{safe_prefix}_{content_hash[:16]}{extension}"
        file_path = self.base_dir / filename

        file_path.write_bytes(data)
        logger.info(f"Stored evidence file: {filename} (SHA256: {content_hash})")

        # Return relative path for portability and content hash
        return str(file_path.relative_to(self.base_dir.parent.parent)), content_hash

    def get_file_bytes(self, storage_reference: str) -> bytes | None:
        path = Path(storage_reference)
        if not path.is_absolute():
            # If relative to project root
            if path.exists():
                return path.read_bytes()
            # Or relative to base_dir
            alt_path = self.base_dir / path.name
            if alt_path.exists():
                return alt_path.read_bytes()
        elif path.exists():
            return path.read_bytes()
        return None


evidence_storage = EvidenceStorage()
