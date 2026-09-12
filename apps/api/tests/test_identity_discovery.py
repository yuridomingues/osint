import asyncio

import httpx

from app.identity_discovery import (
    Candidate,
    _canonical_profile,
    _candidate_name,
    _fetch_candidate,
    _name_handle_variants,
    _normalize_handle,
    _substack_publications_from_mapping,
    _tiktok_search_candidates,
    _youtube_search_candidates,
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



def test_social_content_urls_are_not_profile_candidates():
    assert _canonical_profile("https://www.instagram.com/p/ABC123/") is None
    assert _canonical_profile("https://www.instagram.com/reel/ABC123/") is None
    assert _canonical_profile("https://www.linkedin.com/posts/someone_abc") is None


def test_public_name_generates_small_explainable_handle_variants():
    variants = _name_handle_variants("Yuri Domingues", "dominguesyuri_")
    assert "dominguesyuri_" in variants
    assert "yuridomingues" in variants
    assert "dominguesyuri" in variants
    assert len(variants) <= 8


def test_login_interstitial_does_not_overwrite_search_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            text=(
                "<html><head><title>Instagram</title>"
                "<meta name='description' content='Create an account or log in to Instagram'/>"
                "</head><body></body></html>"
            ),
        )

    candidate = Candidate(
        url="https://www.instagram.com/dominguesyuri_",
        platform="instagram",
        handle="dominguesyuri_",
        title="Yuri Domingues (@dominguesyuri_) • Instagram photos and videos",
        description="dev @oneenergy_news leader @dacc_unifeso",
    )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _fetch_candidate(client, candidate)

    result = asyncio.run(run())
    assert result.title.startswith("Yuri Domingues")
    assert result.description.startswith("dev ")



def test_youtube_native_search_parser_extracts_channel_candidate():
    raw = '''
    <script>
      var ytInitialData = {
        "contents": {
          "twoColumnSearchResultsRenderer": {
            "primaryContents": {
              "sectionListRenderer": {
                "contents": [
                  {
                    "itemSectionRenderer": {
                      "contents": [
                        {
                          "channelRenderer": {
                            "title": {"simpleText": "Yuri Domingues"},
                            "descriptionSnippet": {"runs": [{"text": "Software Engineer"}]},
                            "navigationEndpoint": {
                              "browseEndpoint": {
                                "canonicalBaseUrl": "/@yuridomingues"
                              }
                            }
                          }
                        }
                      ]
                    }
                  }
                ]
              }
            }
          }
        }
      };
    </script>
    '''

    candidates = _youtube_search_candidates(raw)

    assert len(candidates) == 1
    assert candidates[0].handle == "yuridomingues"
    assert candidates[0].title == "Yuri Domingues - YouTube"
    assert candidates[0].description == "Software Engineer"


def test_tiktok_native_search_parser_extracts_public_user():
    raw = '''
    <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">
      {
        "scope": {
          "webapp.user-detail": {
            "userInfo": {
              "user": {
                "uniqueId": "yuridomingues",
                "nickname": "Yuri Domingues",
                "signature": "Software & AI"
              }
            }
          }
        }
      }
    </script>
    '''

    candidates = _tiktok_search_candidates(raw)

    assert len(candidates) == 1
    assert candidates[0].handle == "yuridomingues"
    assert candidates[0].title == "Yuri Domingues (@yuridomingues) | TikTok"
    assert candidates[0].description == "Software & AI"



def test_facebook_threads_and_reddit_urls_are_canonicalized():
    assert _canonical_profile("https://facebook.com/Yuri.Domingues/") == "https://www.facebook.com/Yuri.Domingues"
    assert _canonical_profile("https://www.threads.net/@dominguesyuri_/") == "https://www.threads.net/@dominguesyuri_"
    assert _canonical_profile("https://www.reddit.com/user/yuridomingues/") == "https://www.reddit.com/user/yuridomingues"


def test_facebook_reserved_paths_are_not_profiles():
    assert _canonical_profile("https://www.facebook.com/login/") is None
    assert _canonical_profile("https://www.facebook.com/groups/123/") is None
