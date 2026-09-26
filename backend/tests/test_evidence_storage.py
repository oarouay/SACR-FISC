from pathlib import Path

from app.evidence.storage import EvidenceStorage


def test_evidence_storage_store_and_retrieve(tmp_path: Path):
    storage = EvidenceStorage(base_dir=tmp_path)
    sample_data = b"Simulated PNG Screenshot Byte Data"

    storage_ref, content_hash = storage.store_file(
        data=sample_data,
        filename_prefix="test_overview",
        extension=".png",
    )

    assert len(content_hash) == 64
    assert content_hash == EvidenceStorage.calculate_sha256(sample_data)

    # Retrieve bytes
    retrieved = storage.get_file_bytes(storage_ref)
    assert retrieved == sample_data

    # Nonexistent file returns None
    assert storage.get_file_bytes("nonexistent_file.png") is None
