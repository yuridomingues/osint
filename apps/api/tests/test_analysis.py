from app.analysis import assess_impersonation, correlation_score, text_similarity
from app.models import ImpersonationSignals


def test_similarity_normalizes_punctuation():
    assert text_similarity("yuri.dev", "yuri_dev") == 1.0


def test_username_alone_is_not_identity_certainty():
    score, reasons = correlation_score(1.0, 0.0, False, False)
    assert score == 0.30
    assert reasons


def test_multi_signal_impersonation_can_be_high():
    result = assess_impersonation(ImpersonationSignals(
        handle_similarity=0.97,
        display_name_similarity=0.96,
        reused_visual_identity=True,
        suspicious_external_domain=True,
    ))
    assert result.level == "high"
    assert result.score >= 0.65
