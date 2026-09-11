from app.coordination import analyze_public_posts
from app.models import CaseCreate, PublicPost, TargetType
from app.store import Store


def test_three_accounts_same_content_in_short_window_create_finding(tmp_path):
    store = Store(str(tmp_path / "vigil.db"))
    case = store.create_case(CaseCreate(
        name="Coordination test",
        target="public-dataset",
        target_type=TargetType.PUBLIC_ACCOUNT,
        objective="detect synchronized public content",
        scope_acknowledged=True,
    ))

    posts = [
        PublicPost(
            platform="example",
            author_handle=f"account_{index}",
            text="Same public message https://example.org/x",
            published_at=f"2026-09-11T12:0{index}:00Z",
        )
        for index in range(3)
    ]

    result = analyze_public_posts(store, case.id, posts)
    graph = store.graph(case.id)

    assert result["findings_added"] == 1
    assert graph is not None
    assert graph.findings[0].category == "coordinated-behavior"
    assert "não prova" in graph.findings[0].summary
