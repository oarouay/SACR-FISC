from pathlib import Path

from app.ai.prompts import SYSTEM_INSTRUCTION
from app.models.enums import RegistryStatus, TargetStatus


STATIC_DIR = Path(__file__).parents[1] / "app" / "static"


def test_french_shell_and_language_controls_are_default():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert '<html lang="fr"' in html
    assert "Tableau de bord" in html
    assert "Dossiers à examiner" in html
    assert 'class="gov-header__lang-btn active"' in html
    assert 'title="Bientôt disponible"' in html
    assert html.count('class="gov-header__lang-btn') == 3


def test_status_values_remain_language_neutral():
    assert TargetStatus.PENDING.value == "PENDING"
    assert TargetStatus.COMPLETED.value == "COMPLETED"
    assert TargetStatus.MANUAL_REVIEW.value == "MANUAL_REVIEW"
    assert RegistryStatus.NOT_CHECKED.value == "NOT_CHECKED"
    assert RegistryStatus.MATCHED.value == "MATCHED"


def test_new_ai_output_is_required_in_french():
    assert "rédigés en français administratif clair" in SYSTEM_INSTRUCTION
    assert "Les valeurs d’énumération du schéma restent inchangées" in SYSTEM_INSTRUCTION
