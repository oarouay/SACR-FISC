from app.fiscal_registry.mock import mock_fiscal_registry


def test_search_by_phone():
    # Test with normalized format
    rec = mock_fiscal_registry.search_by_phone("+21698123456")
    assert rec is not None
    assert rec.tax_id == "MAT-TEST-001"
    assert rec.business_name == "Tunis Fashion SARL"

    # Test with unformatted input
    rec_spaces = mock_fiscal_registry.search_by_phone("98 123 456")
    assert rec_spaces is not None
    assert rec_spaces.tax_id == "MAT-TEST-001"


def test_search_by_business_name():
    matches = mock_fiscal_registry.search_by_business_name("Tunis")
    assert len(matches) >= 1
    assert matches[0].tax_id == "MAT-TEST-001"

    matches_electronics = mock_fiscal_registry.search_by_business_name("Electronics")
    assert len(matches_electronics) >= 1
    assert matches_electronics[0].tax_id == "MAT-TEST-002"


def test_search_by_email():
    rec = mock_fiscal_registry.search_by_email("contact@tunisfashion.tn")
    assert rec is not None
    assert rec.tax_id == "MAT-TEST-001"

    # Case insensitive
    rec_upper = mock_fiscal_registry.search_by_email("Contact@TunisFashion.TN")
    assert rec_upper is not None
    assert rec_upper.tax_id == "MAT-TEST-001"


def test_not_found_queries():
    assert mock_fiscal_registry.search_by_phone("+21699999999") is None
    assert mock_fiscal_registry.search_by_email("nonexistent@domain.com") is None
    assert mock_fiscal_registry.search_by_business_name("CompletelyUnregisteredCompanyXYZ") == []
