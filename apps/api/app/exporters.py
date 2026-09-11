from __future__ import annotations

import json
from xml.sax.saxutils import escape

from .models import GraphResponse


def as_json(graph: GraphResponse) -> str:
    return graph.model_dump_json(indent=2)


def as_graphml(graph: GraphResponse) -> str:
    nodes = []
    for e in graph.entities:
        nodes.append(
            f'<node id="{escape(e.id)}"><data key="label">{escape(e.label)}</data>'
            f'<data key="kind">{escape(e.kind)}</data><data key="confidence">{e.confidence}</data></node>'
        )
    edges = []
    for edge in graph.edges:
        edges.append(
            f'<edge id="{escape(edge.id)}" source="{escape(edge.source_id)}" target="{escape(edge.target_id)}">'
            f'<data key="relation">{escape(edge.relation)}</data>'
            f'<data key="confidence">{edge.confidence}</data></edge>'
        )
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="label" for="node" attr.name="label" attr.type="string"/>
  <key id="kind" for="node" attr.name="kind" attr.type="string"/>
  <key id="relation" for="edge" attr.name="relation" attr.type="string"/>
  <key id="confidence" for="all" attr.name="confidence" attr.type="double"/>
  <graph id="vigil" edgedefault="undirected">
""" + "\n".join(nodes + edges) + """
  </graph>
</graphml>
"""
