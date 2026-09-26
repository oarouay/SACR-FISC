from abc import ABC, abstractmethod

from app.fiscal_registry.models import FiscalRecord


class FiscalRegistryInterface(ABC):
    @abstractmethod
    def search_by_phone(self, phone: str) -> FiscalRecord | None:
        """Search for a registered business by phone number."""
        pass

    @abstractmethod
    def search_by_business_name(self, name: str) -> list[FiscalRecord]:
        """Search for registered businesses by exact or partial name."""
        pass

    @abstractmethod
    def search_by_email(self, email: str) -> FiscalRecord | None:
        """Search for a registered business by official email address."""
        pass
