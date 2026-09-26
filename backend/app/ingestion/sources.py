import csv
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.ingestion.normalizer import normalize_facebook_url


@dataclass
class DiscoveredTarget:
    raw_url: str
    canonical_url: str
    priority: int = 0
    source_type: str = "MANUAL"


class TargetSource(ABC):
    @abstractmethod
    def extract_targets(self) -> list[DiscoveredTarget]:
        """Extracts and normalizes target candidate URLs from this source."""
        pass


class ManualTargetSource(TargetSource):
    def __init__(self, url: str, priority: int = 0) -> None:
        self.url = url
        self.priority = priority

    def extract_targets(self) -> list[DiscoveredTarget]:
        canonical = normalize_facebook_url(self.url)
        if not canonical:
            return []
        return [
            DiscoveredTarget(
                raw_url=self.url.strip(),
                canonical_url=canonical,
                priority=self.priority,
                source_type="MANUAL",
            )
        ]


class CsvTargetSource(TargetSource):
    def __init__(self, content: str | bytes, default_priority: int = 0) -> None:
        if isinstance(content, bytes):
            self.content = content.decode("utf-8", errors="replace")
        else:
            self.content = content
        self.default_priority = default_priority

    def extract_targets(self) -> list[DiscoveredTarget]:
        targets: list[DiscoveredTarget] = []
        reader = csv.reader(io.StringIO(self.content))
        for row in reader:
            if not row:
                continue
            # Look for a cell that looks like a URL or column named url
            for cell in row:
                cell_clean = cell.strip()
                if cell_clean.lower() in ["url", "target", "facebook_url", "link"]:
                    # Header row
                    break
                if any(
                    domain in cell_clean
                    for domain in [
                        "facebook.com",
                        "fb.com",
                        "/mock/",
                        "localhost",
                        "127.0.0.1",
                        "backend",
                    ]
                ):
                    canonical = normalize_facebook_url(cell_clean)
                    if canonical:
                        targets.append(
                            DiscoveredTarget(
                                raw_url=cell_clean,
                                canonical_url=canonical,
                                priority=self.default_priority,
                                source_type="CSV_IMPORT",
                            )
                        )
                    break
        return targets
