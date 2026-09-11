from __future__ import annotations

import hashlib
import json
import sqlite3

from .models import (
    AuditEntry,
    Edge,
    Entity,
    EntityClusterCreate,
    GeoObservation,
    GeoObservationCreate,
    Hypothesis,
    HypothesisCreate,
    HypothesisUpdate,
    Note,
    NoteCreate,
    Pin,
    PinCreate,
    RelationReview,
    RelationReviewCreate,
    SavedView,
    SavedViewCreate,
    Snapshot,
    SnapshotCreate,
    TimelineEvent,
    TimelineEventCreate,
    WorkspaceResponse,
    new_id,
    utc_now,
)
from .store import Store


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


def _row_note(row: sqlite3.Row) -> Note:
    data = dict(row)
    data["entity_ids"] = _loads(data["entity_ids"], [])
    data["evidence_ids"] = _loads(data["evidence_ids"], [])
    data["tags"] = _loads(data["tags"], [])
    return Note(**data)


def _row_hypothesis(row: sqlite3.Row) -> Hypothesis:
    data = dict(row)
    for key in ("entity_ids", "evidence_ids", "counterpoints"):
        data[key] = _loads(data[key], [])
    return Hypothesis(**data)


def _row_timeline(row: sqlite3.Row) -> TimelineEvent:
    data = dict(row)
    data["entity_ids"] = _loads(data["entity_ids"], [])
    data["evidence_ids"] = _loads(data["evidence_ids"], [])
    return TimelineEvent(**data)


def _row_geo(row: sqlite3.Row) -> GeoObservation:
    data = dict(row)
    data["evidence_ids"] = _loads(data["evidence_ids"], [])
    data["entity_ids"] = _loads(data["entity_ids"], [])
    return GeoObservation(**data)


def _row_pin(row: sqlite3.Row) -> Pin:
    return Pin(**dict(row))


def _row_view(row: sqlite3.Row) -> SavedView:
    data = dict(row)
    data["filters"] = _loads(data["filters"], {})
    data["layout"] = _loads(data["layout"], {})
    return SavedView(**data)


def _row_review(row: sqlite3.Row) -> RelationReview:
    return RelationReview(**dict(row))


def _row_snapshot(row: sqlite3.Row) -> Snapshot:
    data = dict(row)
    data["payload"] = _loads(data["payload"], {})
    return Snapshot(**data)


def _row_audit(row: sqlite3.Row) -> AuditEntry:
    data = dict(row)
    data["details"] = _loads(data["details"], {})
    return AuditEntry(**data)


def get_workspace(store: Store, case_id: str) -> WorkspaceResponse | None:
    graph = store.graph(case_id)
    if not graph:
        return None
    with store.connect() as db:
        notes = [_row_note(r) for r in db.execute(
            "SELECT * FROM notes WHERE case_id=? ORDER BY updated_at DESC", (case_id,)
        )]
        hypotheses = [_row_hypothesis(r) for r in db.execute(
            "SELECT * FROM hypotheses WHERE case_id=? ORDER BY updated_at DESC", (case_id,)
        )]
        timeline = [_row_timeline(r) for r in db.execute(
            "SELECT * FROM timeline_events WHERE case_id=? ORDER BY event_at ASC", (case_id,)
        )]
        geo = [_row_geo(r) for r in db.execute(
            "SELECT * FROM geo_observations WHERE case_id=? ORDER BY created_at DESC", (case_id,)
        )]
        pins = [_row_pin(r) for r in db.execute(
            "SELECT * FROM pins WHERE case_id=? ORDER BY created_at DESC", (case_id,)
        )]
        saved_views = [_row_view(r) for r in db.execute(
            "SELECT * FROM saved_views WHERE case_id=? ORDER BY created_at DESC", (case_id,)
        )]
        reviews = [_row_review(r) for r in db.execute(
            "SELECT * FROM relation_reviews WHERE case_id=? ORDER BY updated_at DESC", (case_id,)
        )]
        snapshots = [_row_snapshot(r) for r in db.execute(
            "SELECT * FROM snapshots WHERE case_id=? ORDER BY created_at DESC", (case_id,)
        )]
        audit = [_row_audit(r) for r in db.execute(
            "SELECT * FROM audit_log WHERE case_id=? ORDER BY created_at DESC LIMIT 500", (case_id,)
        )]
    return WorkspaceResponse(
        graph=graph,
        notes=notes,
        hypotheses=hypotheses,
        timeline=timeline,
        geo=geo,
        pins=pins,
        saved_views=saved_views,
        relation_reviews=reviews,
        snapshots=snapshots,
        audit=audit,
    )


def create_note(store: Store, case_id: str, payload: NoteCreate) -> Note:
    now = utc_now()
    item = Note(
        id=new_id("note"),
        case_id=case_id,
        body=payload.body,
        entity_ids=payload.entity_ids,
        evidence_ids=payload.evidence_ids,
        tags=payload.tags,
        created_at=now,
        updated_at=now,
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO notes(id,case_id,body,entity_ids,evidence_ids,tags,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                item.id, case_id, item.body, _json(item.entity_ids), _json(item.evidence_ids),
                _json(item.tags), item.created_at, item.updated_at,
            ),
        )
    store.audit(case_id, "note.created", "note", item.id, {"tags": item.tags})
    return item


def delete_note(store: Store, case_id: str, note_id: str) -> bool:
    with store.connect() as db:
        cur = db.execute("DELETE FROM notes WHERE case_id=? AND id=?", (case_id, note_id))
    if cur.rowcount:
        store.audit(case_id, "note.deleted", "note", note_id)
        return True
    return False


def create_hypothesis(store: Store, case_id: str, payload: HypothesisCreate) -> Hypothesis:
    now = utc_now()
    item = Hypothesis(
        id=new_id("hyp"),
        case_id=case_id,
        title=payload.title,
        statement=payload.statement,
        status=payload.status,
        confidence=payload.confidence,
        entity_ids=payload.entity_ids,
        evidence_ids=payload.evidence_ids,
        counterpoints=payload.counterpoints,
        created_at=now,
        updated_at=now,
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO hypotheses(id,case_id,title,statement,status,confidence,entity_ids,evidence_ids,counterpoints,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                item.id, case_id, item.title, item.statement, item.status.value, item.confidence,
                _json(item.entity_ids), _json(item.evidence_ids), _json(item.counterpoints),
                item.created_at, item.updated_at,
            ),
        )
    store.audit(case_id, "hypothesis.created", "hypothesis", item.id, {"status": item.status.value})
    return item


def update_hypothesis(
    store: Store,
    case_id: str,
    hypothesis_id: str,
    payload: HypothesisUpdate,
) -> Hypothesis | None:
    with store.connect() as db:
        row = db.execute(
            "SELECT * FROM hypotheses WHERE case_id=? AND id=?",
            (case_id, hypothesis_id),
        ).fetchone()
        if not row:
            return None
        current = _row_hypothesis(row)
        data = payload.model_dump(exclude_none=True)
        for key, value in data.items():
            setattr(current, key, value)
        current.updated_at = utc_now()
        db.execute(
            "UPDATE hypotheses SET title=?,statement=?,status=?,confidence=?,entity_ids=?,evidence_ids=?,counterpoints=?,updated_at=? "
            "WHERE case_id=? AND id=?",
            (
                current.title, current.statement, current.status.value, current.confidence,
                _json(current.entity_ids), _json(current.evidence_ids), _json(current.counterpoints),
                current.updated_at, case_id, hypothesis_id,
            ),
        )
    store.audit(
        case_id,
        "hypothesis.updated",
        "hypothesis",
        hypothesis_id,
        {"status": current.status.value, "confidence": current.confidence},
    )
    return current


def create_timeline_event(
    store: Store,
    case_id: str,
    payload: TimelineEventCreate,
) -> TimelineEvent:
    item = TimelineEvent(
        id=new_id("event"),
        case_id=case_id,
        title=payload.title,
        description=payload.description,
        event_at=payload.event_at,
        source_url=payload.source_url,
        entity_ids=payload.entity_ids,
        evidence_ids=payload.evidence_ids,
        category=payload.category,
        created_at=utc_now(),
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO timeline_events(id,case_id,title,description,event_at,source_url,entity_ids,evidence_ids,category,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                item.id, case_id, item.title, item.description, item.event_at, item.source_url,
                _json(item.entity_ids), _json(item.evidence_ids), item.category, item.created_at,
            ),
        )
    store.audit(case_id, "timeline.created", "timeline_event", item.id, {"event_at": item.event_at})
    return item


def create_geo_observation(
    store: Store,
    case_id: str,
    payload: GeoObservationCreate,
) -> GeoObservation:
    item = GeoObservation(
        id=new_id("geo"),
        case_id=case_id,
        label=payload.label,
        city=payload.city,
        region=payload.region,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        source_url=payload.source_url,
        evidence_ids=payload.evidence_ids,
        entity_ids=payload.entity_ids,
        category=payload.category,
        created_at=utc_now(),
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO geo_observations(id,case_id,label,city,region,country,latitude,longitude,source_url,evidence_ids,entity_ids,category,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                item.id, case_id, item.label, item.city, item.region, item.country,
                item.latitude, item.longitude, item.source_url, _json(item.evidence_ids),
                _json(item.entity_ids), item.category, item.created_at,
            ),
        )
    store.audit(
        case_id,
        "geo.created",
        "geo_observation",
        item.id,
        {"precision": "city-level", "city": item.city, "country": item.country},
    )
    return item


def create_pin(store: Store, case_id: str, payload: PinCreate) -> Pin:
    item = Pin(
        id=new_id("pin"),
        case_id=case_id,
        object_type=payload.object_type,
        object_id=payload.object_id,
        label=payload.label,
        created_at=utc_now(),
    )
    with store.connect() as db:
        existing = db.execute(
            "SELECT * FROM pins WHERE case_id=? AND object_type=? AND object_id=?",
            (case_id, item.object_type, item.object_id),
        ).fetchone()
        if existing:
            return _row_pin(existing)
        db.execute(
            "INSERT INTO pins(id,case_id,object_type,object_id,label,created_at) VALUES(?,?,?,?,?,?)",
            (item.id, case_id, item.object_type, item.object_id, item.label, item.created_at),
        )
    store.audit(case_id, "pin.created", "pin", item.id, {"object_type": item.object_type})
    return item


def delete_pin(store: Store, case_id: str, pin_id: str) -> bool:
    with store.connect() as db:
        cur = db.execute("DELETE FROM pins WHERE case_id=? AND id=?", (case_id, pin_id))
    if cur.rowcount:
        store.audit(case_id, "pin.deleted", "pin", pin_id)
        return True
    return False


def create_saved_view(
    store: Store,
    case_id: str,
    payload: SavedViewCreate,
) -> SavedView:
    item = SavedView(
        id=new_id("view"),
        case_id=case_id,
        name=payload.name,
        filters=payload.filters,
        layout=payload.layout,
        created_at=utc_now(),
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO saved_views(id,case_id,name,filters,layout,created_at) VALUES(?,?,?,?,?,?)",
            (item.id, case_id, item.name, _json(item.filters), _json(item.layout), item.created_at),
        )
    store.audit(case_id, "view.created", "saved_view", item.id, {"name": item.name})
    return item


def review_relation(
    store: Store,
    case_id: str,
    edge_id: str,
    payload: RelationReviewCreate,
) -> RelationReview:
    now = utc_now()
    with store.connect() as db:
        existing = db.execute(
            "SELECT * FROM relation_reviews WHERE case_id=? AND edge_id=?",
            (case_id, edge_id),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE relation_reviews SET state=?,comment=?,updated_at=? WHERE case_id=? AND edge_id=?",
                (payload.state, payload.comment, now, case_id, edge_id),
            )
            review_id = existing["id"]
            created_at = existing["created_at"]
        else:
            review_id = new_id("review")
            created_at = now
            db.execute(
                "INSERT INTO relation_reviews(id,case_id,edge_id,state,comment,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (review_id, case_id, edge_id, payload.state, payload.comment, created_at, now),
            )
    item = RelationReview(
        id=review_id,
        case_id=case_id,
        edge_id=edge_id,
        state=payload.state,
        comment=payload.comment,
        created_at=created_at,
        updated_at=now,
    )
    store.audit(case_id, "edge.reviewed", "edge", edge_id, {"state": payload.state})
    return item


def create_cluster(
    store: Store,
    case_id: str,
    payload: EntityClusterCreate,
) -> Entity:
    graph = store.graph(case_id)
    if not graph:
        raise ValueError("Case not found")
    entity_by_id = {item.id: item for item in graph.entities}
    missing = [item for item in payload.entity_ids if item not in entity_by_id]
    if missing:
        raise ValueError("Unknown entity IDs: " + ", ".join(missing))

    cluster = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind="entity_cluster",
        label=payload.label,
        canonical_key=f"cluster:{new_id('key')}",
        properties={
            "member_ids": payload.entity_ids,
            "rationale": payload.rationale,
            "analyst_created": True,
        },
        confidence=0.5,
    )
    cluster, _ = store.upsert_entity(cluster)
    for member_id in payload.entity_ids:
        store.add_edge(
            Edge(
                id=new_id("edge"),
                case_id=case_id,
                source_id=member_id,
                target_id=cluster.id,
                relation="cluster_member",
                confidence=0.5,
                rationale=[payload.rationale or "Agrupamento analítico manual"],
                evidence_ids=[],
            )
        )
    store.audit(
        case_id,
        "cluster.created",
        "entity_cluster",
        cluster.id,
        {"members": payload.entity_ids, "rationale": payload.rationale},
    )
    return cluster


def detach_cluster_member(
    store: Store,
    case_id: str,
    cluster_id: str,
    entity_id: str,
) -> bool:
    with store.connect() as db:
        row = db.execute(
            "SELECT id FROM edges WHERE case_id=? AND source_id=? AND target_id=? AND relation='cluster_member'",
            (case_id, entity_id, cluster_id),
        ).fetchone()
    if not row:
        return False
    return store.delete_edge(case_id, row["id"])


def create_snapshot(
    store: Store,
    case_id: str,
    payload: SnapshotCreate,
) -> Snapshot:
    evidence = store.get_evidence(case_id, payload.evidence_id)
    if not evidence:
        raise ValueError("Evidence not found")
    snapshot_payload = evidence.model_dump()
    canonical = json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    item = Snapshot(
        id=new_id("snap"),
        case_id=case_id,
        evidence_id=evidence.id,
        payload=snapshot_payload,
        content_hash=hashlib.sha256(canonical).hexdigest(),
        created_at=utc_now(),
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO snapshots(id,case_id,evidence_id,payload,content_hash,created_at) VALUES(?,?,?,?,?,?)",
            (
                item.id, case_id, item.evidence_id, _json(item.payload),
                item.content_hash, item.created_at,
            ),
        )
    store.audit(case_id, "snapshot.created", "snapshot", item.id, {"evidence_id": evidence.id})
    return item


def auto_timeline_from_evidence(store: Store, case_id: str) -> int:
    graph = store.graph(case_id)
    if not graph:
        return 0
    added = 0
    with store.connect() as db:
        for evidence in graph.evidence:
            exists = db.execute(
                "SELECT 1 FROM timeline_events WHERE case_id=? AND evidence_ids=? LIMIT 1",
                (case_id, _json([evidence.id])),
            ).fetchone()
            if exists:
                continue
            item = TimelineEvent(
                id=new_id("event"),
                case_id=case_id,
                title=evidence.source,
                description=evidence.excerpt or evidence.collector,
                event_at=evidence.observed_at,
                source_url=evidence.source_url,
                entity_ids=[],
                evidence_ids=[evidence.id],
                category="evidence",
                created_at=utc_now(),
            )
            db.execute(
                "INSERT INTO timeline_events(id,case_id,title,description,event_at,source_url,entity_ids,evidence_ids,category,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    item.id, case_id, item.title, item.description, item.event_at, item.source_url,
                    "[]", _json(item.evidence_ids), item.category, item.created_at,
                ),
            )
            added += 1
    if added:
        store.audit(case_id, "timeline.generated", "case", case_id, {"events_added": added})
    return added
