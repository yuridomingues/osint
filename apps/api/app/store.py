from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Case, CaseCreate, Edge, Entity, Evidence, Finding, GraphResponse, new_id, utc_now


class Store:
    def __init__(self, path: str | None = None) -> None:
        default_path = "/tmp/vigil.db" if os.getenv("VERCEL") else "./data/vigil.db"
        self.path = path or os.getenv("VIGIL_DB_PATH", default_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def _init(self) -> None:
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS cases(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, target TEXT NOT NULL,
              target_type TEXT NOT NULL, objective TEXT NOT NULL,
              created_at TEXT NOT NULL, status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entities(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kind TEXT NOT NULL,
              label TEXT NOT NULL, canonical_key TEXT NOT NULL,
              properties TEXT NOT NULL, confidence REAL NOT NULL,
              created_at TEXT NOT NULL, UNIQUE(case_id, canonical_key)
            );

            CREATE TABLE IF NOT EXISTS edges(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
              target_id TEXT NOT NULL, relation TEXT NOT NULL, confidence REAL NOT NULL,
              rationale TEXT NOT NULL, evidence_ids TEXT NOT NULL, created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source TEXT NOT NULL,
              collector TEXT NOT NULL, source_url TEXT, excerpt TEXT NOT NULL,
              metadata TEXT NOT NULL, reliability REAL NOT NULL,
              content_hash TEXT, observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS findings(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, category TEXT NOT NULL,
              severity TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
              confidence REAL NOT NULL, evidence_ids TEXT NOT NULL, created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, body TEXT NOT NULL,
              entity_ids TEXT NOT NULL, evidence_ids TEXT NOT NULL, tags TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hypotheses(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
              statement TEXT NOT NULL, status TEXT NOT NULL, confidence REAL NOT NULL,
              entity_ids TEXT NOT NULL, evidence_ids TEXT NOT NULL,
              counterpoints TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS timeline_events(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
              description TEXT NOT NULL, event_at TEXT NOT NULL, source_url TEXT,
              entity_ids TEXT NOT NULL, evidence_ids TEXT NOT NULL,
              category TEXT NOT NULL, created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS geo_observations(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, label TEXT NOT NULL,
              city TEXT NOT NULL, region TEXT NOT NULL, country TEXT NOT NULL,
              latitude REAL NOT NULL, longitude REAL NOT NULL, source_url TEXT,
              evidence_ids TEXT NOT NULL, entity_ids TEXT NOT NULL,
              category TEXT NOT NULL, created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pins(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL,
              object_id TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(case_id, object_type, object_id)
            );

            CREATE TABLE IF NOT EXISTS saved_views(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, name TEXT NOT NULL,
              filters TEXT NOT NULL, layout TEXT NOT NULL, created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relation_reviews(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, edge_id TEXT NOT NULL,
              state TEXT NOT NULL, comment TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(case_id, edge_id)
            );

            CREATE TABLE IF NOT EXISTS snapshots(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
              payload TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log(
              id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action TEXT NOT NULL,
              object_type TEXT NOT NULL, object_id TEXT, details TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_entities_case ON entities(case_id);
            CREATE INDEX IF NOT EXISTS idx_edges_case ON edges(case_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
            CREATE INDEX IF NOT EXISTS idx_findings_case ON findings(case_id);
            CREATE INDEX IF NOT EXISTS idx_notes_case ON notes(case_id);
            CREATE INDEX IF NOT EXISTS idx_hypotheses_case ON hypotheses(case_id);
            CREATE INDEX IF NOT EXISTS idx_timeline_case ON timeline_events(case_id);
            CREATE INDEX IF NOT EXISTS idx_geo_case ON geo_observations(case_id);
            CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id);
            """)

            columns = {row["name"] for row in db.execute("PRAGMA table_info(evidence)")}
            if "content_hash" not in columns:
                db.execute("ALTER TABLE evidence ADD COLUMN content_hash TEXT")

            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_edge_relation "
                "ON edges(case_id, source_id, target_id, relation)"
            )

    def audit(
        self,
        case_id: str,
        action: str,
        object_type: str,
        object_id: str | None = None,
        details: dict | None = None,
    ) -> str:
        audit_id = new_id("audit")
        with self.connect() as db:
            db.execute(
                "INSERT INTO audit_log(id,case_id,action,object_type,object_id,details,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    audit_id,
                    case_id,
                    action,
                    object_type,
                    object_id,
                    json.dumps(details or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )
        return audit_id

    def create_case(self, payload: CaseCreate) -> Case:
        case = Case(
            id=new_id("case"),
            name=payload.name,
            target=payload.target,
            target_type=payload.target_type,
            objective=payload.objective,
            created_at=utc_now(),
        )
        with self.connect() as db:
            db.execute(
                "INSERT INTO cases(id,name,target,target_type,objective,created_at,status) VALUES(?,?,?,?,?,?,?)",
                (case.id, case.name, case.target, case.target_type.value, case.objective, case.created_at, case.status),
            )
        self.audit(case.id, "case.created", "case", case.id, {"target_type": case.target_type.value})
        return case

    def list_cases(self) -> list[Case]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
        return [Case(**dict(r)) for r in rows]

    def get_case(self, case_id: str) -> Case | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return Case(**dict(row)) if row else None

    def set_status(self, case_id: str, status: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE cases SET status=? WHERE id=?", (status, case_id))

    def upsert_entity(self, item: Entity) -> tuple[Entity, bool]:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM entities WHERE case_id=? AND canonical_key=?",
                (item.case_id, item.canonical_key),
            ).fetchone()
            if row:
                return self._entity(row), False
            db.execute(
                "INSERT INTO entities(id,case_id,kind,label,canonical_key,properties,confidence,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    item.id,
                    item.case_id,
                    item.kind,
                    item.label,
                    item.canonical_key,
                    json.dumps(item.properties, ensure_ascii=False),
                    item.confidence,
                    item.created_at,
                ),
            )
        return item, True

    def add_edge(self, item: Edge) -> Edge:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO edges(id,case_id,source_id,target_id,relation,confidence,rationale,evidence_ids,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    item.id,
                    item.case_id,
                    item.source_id,
                    item.target_id,
                    item.relation,
                    item.confidence,
                    json.dumps(item.rationale, ensure_ascii=False),
                    json.dumps(item.evidence_ids),
                    item.created_at,
                ),
            )
        return item

    def delete_edge(self, case_id: str, edge_id: str) -> bool:
        with self.connect() as db:
            cur = db.execute("DELETE FROM edges WHERE case_id=? AND id=?", (case_id, edge_id))
        if cur.rowcount:
            self.audit(case_id, "edge.deleted", "edge", edge_id)
            return True
        return False

    def add_evidence(self, item: Evidence) -> Evidence:
        with self.connect() as db:
            db.execute(
                "INSERT INTO evidence(id,case_id,source,collector,source_url,excerpt,metadata,reliability,content_hash,observed_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    item.id,
                    item.case_id,
                    item.source,
                    item.collector,
                    item.source_url,
                    item.excerpt,
                    json.dumps(item.metadata, ensure_ascii=False),
                    item.reliability,
                    item.content_hash,
                    item.observed_at,
                ),
            )
        return item

    def get_evidence(self, case_id: str, evidence_id: str) -> Evidence | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM evidence WHERE case_id=? AND id=?",
                (case_id, evidence_id),
            ).fetchone()
        return self._evidence(row) if row else None

    def add_finding(self, item: Finding) -> Finding:
        with self.connect() as db:
            db.execute(
                "INSERT INTO findings(id,case_id,category,severity,title,summary,confidence,evidence_ids,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    item.id,
                    item.case_id,
                    item.category,
                    item.severity,
                    item.title,
                    item.summary,
                    item.confidence,
                    json.dumps(item.evidence_ids),
                    item.created_at,
                ),
            )
        return item

    def graph(self, case_id: str) -> GraphResponse | None:
        case = self.get_case(case_id)
        if not case:
            return None
        with self.connect() as db:
            entities = [self._entity(r) for r in db.execute("SELECT * FROM entities WHERE case_id=?", (case_id,))]
            edges = [self._edge(r) for r in db.execute("SELECT * FROM edges WHERE case_id=?", (case_id,))]
            evidence = [self._evidence(r) for r in db.execute("SELECT * FROM evidence WHERE case_id=?", (case_id,))]
            findings = [self._finding(r) for r in db.execute("SELECT * FROM findings WHERE case_id=?", (case_id,))]
        return GraphResponse(case=case, entities=entities, edges=edges, evidence=evidence, findings=findings)

    @staticmethod
    def _entity(row: sqlite3.Row) -> Entity:
        data = dict(row)
        data["properties"] = json.loads(data["properties"])
        return Entity(**data)

    @staticmethod
    def _edge(row: sqlite3.Row) -> Edge:
        data = dict(row)
        data["rationale"] = json.loads(data["rationale"])
        data["evidence_ids"] = json.loads(data["evidence_ids"])
        return Edge(**data)

    @staticmethod
    def _evidence(row: sqlite3.Row) -> Evidence:
        data = dict(row)
        data["metadata"] = json.loads(data["metadata"])
        return Evidence(**data)

    @staticmethod
    def _finding(row: sqlite3.Row) -> Finding:
        data = dict(row)
        data["evidence_ids"] = json.loads(data["evidence_ids"])
        return Finding(**data)
