from app.identity_discovery import (
    Candidate,
    _canonical_profile,
    _candidate_name,
    _normalize_handle,
    _substack_publications_from_mapping,
    score_candidate,
)


def test_username_similarity_alone_is_not_identity_proof():
    candidate = Candidate(
        url="https://x.com/dominguesyuri_",
        platform="x",
        handle="dominguesyuri_",
        title="dominguesyuri_ on X",
    )

    score, reasons, strong = score_candidate(
        "dominguesyuri_",
        set(),
        set(),
        candidate,
    )

    assert score < 0.45
    assert not strong
    assert any("username" in reason for reason in reasons)


def test_different_substack_handle_can_correlate_via_public_backlink():
    candidate = Candidate(
        url="https://substack.com/@completelydifferent",
        platform="substack",
        handle="completelydifferent",
        title="Yuri Domingues | Substack",
        outbound_links={"https://github.com/yuridomingues"},
    )

    score, reasons, strong = score_candidate(
        "dominguesyuri_",
        {"Yuri Domingues"},
        {"https://github.com/yuridomingues"},
        candidate,
    )

    assert score >= 0.70
    assert strong
    assert any("links back" in reason for reason in reasons)


def test_github_history_is_strong_even_when_username_is_different():
    candidate = Candidate(
        url="https://substack.com/@notthesameusername",
        platform="substack",
        handle="notthesameusername",
        provenance="github_history",
    )

    score, reasons, strong = score_candidate(
        "dominguesyuri_",
        set(),
        set(),
        candidate,
    )

    assert score >= 0.60
    assert strong
    assert any("Git history" in reason for reason in reasons)


def test_substack_and_x_urls_are_canonicalized():
    assert _canonical_profile("https://substack.com/@YuriDomingues/") == "https://substack.com/@YuriDomingues"
    assert _canonical_profile("https://twitter.com/dominguesyuri_/status/123") == "https://x.com/dominguesyuri_"


def test_candidate_name_and_handle_normalization():
    assert _candidate_name("Yuri Domingues | Substack", "somethingelse") == "Yuri Domingues"
    assert _normalize_handle("DominguesYuri_") == "dominguesyuri"


def test_name_plus_bio_can_support_different_handle_candidate():
    candidate = Candidate(
        url="https://substack.com/@unrelatedhandle",
        platform="substack",
        handle="unrelatedhandle",
        title="Yuri Domingues | Substack",
        description="Software engineering, AI engineering, OSINT and cybersecurity.",
    )

    score, reasons, strong = score_candidate(
        "dominguesyuri_",
        {"Yuri Domingues"},
        set(),
        candidate,
        anchor_texts={"Software engineering, AI engineering, OSINT and cybersecurity."},
    )

    assert score >= 0.55
    assert strong
    assert any("biography" in reason for reason in reasons)


def test_unanchored_github_history_is_not_strong_identity_evidence():
    candidate = Candidate(
        url="https://x.com/someotheraccount",
        platform="x",
        handle="someotheraccount",
        provenance="github_history_unanchored",
    )

    score, reasons, strong = score_candidate(
        "dominguesyuri_",
        {"Yuri Domingues"},
        {"https://www.instagram.com/dominguesyuri_"},
        candidate,
    )

    assert score < 0.45
    assert not strong
    assert not any("Git history" in reason for reason in reasons)


def test_substack_publication_is_separate_from_author_profile():
    data = {
        "handle": "yuridomingues",
        "name": "Yuri Domingues",
        "publicationUsers": [
            {
                "publication_id": 42,
                "name": "Escassez",
                "subdomain": "escassez",
                "description": "Public newsletter description",
            }
        ],
    }

    publications = _substack_publications_from_mapping(data)

    assert len(publications) == 1
    assert publications[0]["name"] == "Escassez"
    assert publications[0]["url"] == "https://escassez.substack.com"
    assert publications[0]["publication_id"] == 42
