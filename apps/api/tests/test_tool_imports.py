from app.models import CaseCreate, TargetType
from app.store import Store
from app.tool_imports import import_tool_export


def make_store(tmp_path):
    return Store(str(tmp_path / "vigil.db"))


def make_case(store):
    return store.create_case(CaseCreate(
        name="Import test",
        target="public-example",
        target_type=TargetType.PUBLIC_ACCOUNT,
        objective="test",
        scope_acknowledged=True,
    ))


def test_sherlock_only_imports_claimed_rows(tmp_path):
    store = make_store(tmp_path)
    case = make_case(store)
    csv = (
        "username,name,url_main,url_user,exists,http_status,response_time_s\n"
        "alice,GitHub,https://github.com,https://github.com/alice,Claimed,200,0.1\n"
        "alice,Reddit,https://reddit.com,https://reddit.com/u/alice,Available,404,0.2\n"
    )

    result = import_tool_export(store, case.id, "sherlock_csv", csv)
    graph = store.graph(case.id)

    assert result["records_parsed"] == 1
    assert graph is not None
    assert len([entity for entity in graph.entities if entity.kind == "account"]) == 1


def test_maigret_object_map_import(tmp_path):
    store = make_store(tmp_path)
    case = make_case(store)
    data = """{
      "GitHub": {
        "username": "alice",
        "url_user": "https://github.com/alice",
        "status": "Claimed"
      }
    }"""

    result = import_tool_export(store, case.id, "maigret_json", data)

    assert result["records_parsed"] == 1
    assert result["evidence_added"] == 1
