import json
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger
from app.extraction.phones import PhoneExtractor
from app.fiscal_registry.interface import FiscalRegistryInterface
from app.fiscal_registry.models import FiscalRecord


class MockFiscalRegistry(FiscalRegistryInterface):
    def __init__(self, fixtures_path: Path | None = None) -> None:
        self.fixtures_path = fixtures_path or (settings.fixtures_path / "fiscal_registry.json")
        self._records: list[FiscalRecord] = []
        self._load_records()

    def _load_records(self) -> None:
        if self.fixtures_path.exists():
            try:
                data = json.loads(self.fixtures_path.read_text(encoding="utf-8"))
                self._records = [FiscalRecord(**item) for item in data]
                logger.info(
                    f"Loaded {len(self._records)} fiscal registry records from {self.fixtures_path}"
                )
            except Exception as e:
                logger.error(f"Failed to load fiscal registry fixtures: {e}")
                self._records = []
        else:
            logger.warning(f"Fiscal registry fixture not found at {self.fixtures_path}")
            self._records = []

    def search_by_phone(self, phone: str) -> FiscalRecord | None:
        norm = PhoneExtractor.normalize_phone(phone) or phone.replace(" ", "").strip()
        for record in self._records:
            if record.phone:
                rec_norm = (
                    PhoneExtractor.normalize_phone(record.phone)
                    or record.phone.replace(" ", "").strip()
                )
                if rec_norm == norm:
                    return record
        return None

    def search_by_business_name(self, name: str) -> list[FiscalRecord]:
        query = name.lower().strip()
        matches: list[FiscalRecord] = []
        for record in self._records:
            if query in record.business_name.lower():
                matches.append(record)
        return matches

    def search_by_email(self, email: str) -> FiscalRecord | None:
        norm = email.lower().strip()
        for record in self._records:
            if record.email and record.email.lower().strip() == norm:
                return record
        return None


mock_fiscal_registry = MockFiscalRegistry()
