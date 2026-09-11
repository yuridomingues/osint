from app.models import CaseCreate, TargetType
from app.store import Store
from app.tool_imports import import_tool_export


def make_store(tmp_path):
    return Store(str(tmp_path / "vigil.db"))


def make_domain_case(store):
    return store.create_case(CaseCreate(
        name="Infra import",
        target="example.org",
        target_type=TargetType.DOMAIN,
        objective="Normalize passive infrastructure exports",
        scope_acknowledged=True,
    ))


def test_subfinder_jsonl_import(tmp_path):
    store = make_store(tmp_path)
    case = make_domain_case(store)
    content = (
        '{"host":"api.example.org","input":"example.org","source":"crtsh"}\n'
        '{"host":"portal.example.org","input":"example.org","source":"dnsdumpster"}'
    )

    result = import_tool_export(store, case.id, "subfinder_jsonl", content)
    graph = store.graph(case.id)

    assert result["records_parsed"] == 2
    assert graph is not None
    assert len([e for e in graph.entities if e.kind == "hostname"]) == 2
    assert len(graph.evidence) == 2


def test_amass_import_links_hostname_to_ip(tmp_path):
    store = make_store(tmp_path)
    case = make_domain_case(store)
    content = (
        '{"name":"api.example.org","domain":"example.org",'
        '"addresses":[{"ip":"203.0.113.10","cidr":"203.0.113.0/24","asn":64500}]}'
    )

    result = import_tool_export(store, case.id, "amass_json", content)
    graph = store.graph(case.id)

    assert result["records_parsed"] == 1
    assert graph is not None
    assert any(e.kind == "ip" for e in graph.entities)
    assert any(edge.relation == "resolves_to" for edge in graph.edges)


def test_spiderfoot_skips_person_contact_events(tmp_path):
    store = make_store(tmp_path)
    case = make_domain_case(store)
    content = (
        "Updated,Type,Module,Source,F/P,Data\n"
        "2026-09-11,INTERNET_NAME,sfp_dnsresolve,example.org,,api.example.org\n"
        "2026-09-11,EMAILADDR,sfp_accounts,example.org,,person@example.org\n"
    )

    result = import_tool_export(store, case.id, "spiderfoot_csv", content)
    graph = store.graph(case.id)

    assert result["records_parsed"] == 1
    assert graph is not None
    labels = {entity.label for entity in graph.entities}
    assert "api.example.org" in labels
    assert "person@example.org" not in labels
