from app.models import (
    CaseCreate,
    Entity,
    EntityClusterCreate,
    GeoObservationCreate,
    HypothesisCreate,
    NoteCreate,
    PinCreate,
    SnapshotCreate,
    TargetType,
    new_id,
)
from app.reports import report_markdown
from app.store import Store
from app.workspace import (
    create_cluster,
    create_geo_observation,
    create_hypothesis,
    create_note,
    create_pin,
    create_snapshot,
    get_workspace,
)


def make_store(tmp_path):
    return Store(str(tmp_path / "vigil.db"))


def make_case(store):
    return store.create_case(CaseCreate(
        name="Workspace test",
        target="example.org",
        target_type=TargetType.DOMAIN,
        objective="Test professional analyst workspace",
        scope_acknowledged=True,
    ))


def test_workspace_persists_notes_hypotheses_and_pins(tmp_path):
    store = make_store(tmp_path)
    case = make_case(store)

    note = create_note(store, case.id, NoteCreate(
        body="Analyst note",
        tags=["verification"],
    ))
    hypothesis = create_hypothesis(store, case.id, HypothesisCreate(
        title="Shared infrastructure",
        statement="Two observations may share public infrastructure.",
        confidence=0.55,
    ))
    create_pin(store, case.id, PinCreate(
        object_type="hypothesis",
        object_id=hypothesis.id,
        label=hypothesis.title,
    ))

    workspace = get_workspace(store, case.id)

    assert workspace is not None
    assert workspace.notes[0].id == note.id
    assert workspace.hypotheses[0].id == hypothesis.id
    assert workspace.pins[0].object_id == hypothesis.id
    assert any(entry.action == "hypothesis.created" for entry in workspace.audit)


def test_geo_is_reduced_to_city_level_precision(tmp_path):
    store = make_store(tmp_path)
    case = make_case(store)

    point = create_geo_observation(store, case.id, GeoObservationCreate(
        label="Public city context",
        city="Example City",
        country="BR",
        latitude=-22.987654,
        longitude=-43.123456,
    ))

    assert point.latitude == -22.99
    assert point.longitude == -43.12


def test_cluster_is_non_destructive_and_links_members(tmp_path):
    store = make_store(tmp_path)
    case = make_case(store)

    first, _ = store.upsert_entity(Entity(
        id=new_id("ent"),
        case_id=case.id,
        kind="domain",
        label="a.example.org",
        canonical_key="domain:a.example.org",
        confidence=0.8,
    ))
    second, _ = store.upsert_entity(Entity(
        id=new_id("ent"),
        case_id=case.id,
        kind="domain",
        label="b.example.org",
        canonical_key="domain:b.example.org",
        confidence=0.8,
    ))

    cluster = create_cluster(store, case.id, EntityClusterCreate(
        label="Possible shared set",
        entity_ids=[first.id, second.id],
        rationale="Manual analyst grouping",
    ))
    graph = store.graph(case.id)

    assert graph is not None
    assert cluster.kind == "entity_cluster"
    assert first.id in {entity.id for entity in graph.entities}
    assert second.id in {entity.id for entity in graph.entities}
    memberships = [edge for edge in graph.edges if edge.relation == "cluster_member"]
    assert len(memberships) == 2


def test_snapshot_and_curated_report(tmp_path):
    from app.models import Evidence

    store = make_store(tmp_path)
    case = make_case(store)
    evidence = Evidence(
        id=new_id("ev"),
        case_id=case.id,
        source="Example public registry",
        collector="fixture",
        source_url="https://example.org/source",
        excerpt="Public evidence fixture",
        reliability=0.8,
    )
    store.add_evidence(evidence)

    snapshot = create_snapshot(store, case.id, SnapshotCreate(evidence_id=evidence.id))
    create_pin(store, case.id, PinCreate(
        object_type="evidence",
        object_id=evidence.id,
        label=evidence.source,
    ))

    workspace = get_workspace(store, case.id)
    assert workspace is not None
    assert len(snapshot.content_hash) == 64

    report = report_markdown(workspace, curated_only=True)
    assert "Example public registry" in report
    assert "Workspace test" in report
