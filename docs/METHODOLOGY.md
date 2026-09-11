# Investigation methodology

VIGIL uses an evidence-first workflow inspired by professional link-analysis and intelligence-analysis practice.

## 1. Scope before collection

Every case must define:

- target;
- target type;
- objective;
- legitimate public-source scope.

The objective should be phrased as a question that can be answered by evidence, for example: "Are these public accounts plausibly related to the same brand identity?" rather than "Find everything about this person."

## 2. Separate observation from assessment

An **observation** is something directly present in a public source. An **assessment** is an interpretation.

Examples:

- observation: two public profiles link to the same domain;
- assessment: the profiles may be related;
- observation: three accounts publish identical normalized text within 12 minutes;
- assessment: this is an indicator of coordination.

VIGIL stores these separately.

## 3. Provenance

Evidence records contain:

- source;
- collector/import adapter;
- source URL when available;
- observation time;
- reliability;
- SHA-256 content hash;
- source-specific metadata.

The hash does not prove that a web page was truthful. It proves which normalized evidence record was used by the case.

## 4. Correlation

Identity correlation is deliberately conservative.

Strong signals include:

- the same externally controlled domain;
- reused public media hash;
- independent corroboration from multiple public sources.

Weak signals include:

- similar handle;
- similar display name;
- similar biography wording.

A weak signal alone is not enough to produce an identity relation.

## 5. Fake / impersonation

Impersonation scoring is multi-signal and explainable. The score combines handle/name similarity, visual-identity reuse, official-link reuse, suspicious external domains, profile sparsity and synchronized behavior.

The analyst still owns the conclusion. The score is triage, not a verdict.

## 6. Coordinated behavior / influence-operation analysis

The current defensive detector looks for identical normalized public content from at least three accounts inside a short time window.

A coordination finding means:

- a measurable behavioral pattern exists;
- the pattern deserves analyst review.

It does **not** prove common control, malicious intent, a specific actor, or a "psyop".

Future versions should add narrative clustering, URL-sharing networks, burst detection and cross-platform temporal analysis while preserving the same distinction.

## 7. Confidence language

Suggested interpretation:

| Confidence | Meaning |
|---|---|
| < 0.35 | weak / insufficient |
| 0.35–0.64 | plausible; needs corroboration |
| 0.65–0.84 | strong multi-signal support |
| >= 0.85 | very strong support, still not absolute proof |

## 8. Reporting

A professional report should include:

1. objective and scope;
2. key findings;
3. graph snapshots;
4. evidence ledger;
5. confidence/rationale;
6. alternative explanations;
7. collection limitations;
8. timestamps and export hashes.
