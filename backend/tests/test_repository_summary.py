from app.repository import dashboard_summary, finance_summary


def test_dashboard_summary(db_session):
    summary = dashboard_summary(db_session)
    assert summary["total_revenue"] == 48000
    assert summary["total_profit"] == 8000
    assert summary["active_operations"] == 1
    assert summary["delivery_success_rate"] == 50.0
    assert summary["risky_operations"] == 2


def test_finance_summary(db_session):
    summary = finance_summary(db_session)
    assert summary["current_cash"] == 510000
    assert summary["pending_collections"] == 63000
    assert summary["projected_outflow"] == 85000
    assert summary["projected_cash_15_days"] == 488000
    assert summary["total_profit"] == 8000
