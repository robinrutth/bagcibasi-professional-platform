from datetime import date, timedelta

from app.calculations import calculate_operation


def test_calculate_operation_returns_expected_fields():
    result = calculate_operation("Manisa", "İstanbul", "Tekstil", 14, date.today() + timedelta(days=3))
    assert result["distance_km"] > 0
    assert result["vehicle_type"] in {"Kamyonet", "Kamyon", "Tır"}
    assert result["invoice_amount"] >= result["cost_amount"]
    assert result["profit_amount"] == round(result["invoice_amount"] - result["cost_amount"], 2)
    assert result["co2_kg"] > 0
    assert result["risk_level"] in {"Düşük", "Orta", "Yüksek"}

