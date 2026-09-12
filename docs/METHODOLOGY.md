# Investigation methodology

VIGIL uses an evidence-first workflow heavily informed by Bellingcat's open-source investigation practice, while adapting it to a software workbench.

The operational sequence is:

```text
Identification
   ↓
Collection + Preservation
   ↓
Verification
   ↓
Analysis
   ↓
Review + Confirmation
   ↓
Presentation
```

The stages are not a rigid waterfall. An analyst may return to collection after discovering a new pivot, but every conclusion should remain traceable back to preserved evidence.

## 1. Identification: define the question before collecting

Every case must define:

- target;
- target type;
- objective / intelligence question;
- legitimate public-source scope;
- what would count as confirming or disconfirming evidence.

The objective should be phrased as a falsifiable question, for example:

- "Are these public accounts plausibly related to the same public identity?"
- "Does this image appear elsewhere on the public web?"
- "Do these posts show measurable coordination?"
- "What public infrastructure relationships can be established for this organization?"

Avoid undefined objectives such as "find everything about this person."

## 2. Collection + preservation

Collection is not complete until the source can be revisited or its state can be reconstructed.

For each item, VIGIL should preserve as much as the collector allows:

- source URL;
- collector/provider;
- observation time;
- redirect chain when relevant;
- normalized metadata;
- content hash;
- raw or archived artifact when available;
- collector version / method;
- provider-specific identifiers.

For uploaded files, hash the original bytes before any transformation.

For volatile web content, the long-term design target is:

```text
URL
 ↓
raw HTML / media
 ↓
screenshot
 ↓
headers + redirect chain
 ↓
SHA-256 manifest
 ↓
immutable object storage / WARC-style bundle
```

Preservation is part of verification, not an optional reporting step.

## 3. Verification: test the source and the claim separately

A source being authentic does not make every claim on that source true.

Verification asks:

1. Is this the source we think it is?
2. Has the content been altered or reposted?
3. When was it observed?
4. Is there independent corroboration?
5. Could there be a simpler alternative explanation?

Useful verification techniques include:

- reverse-image search;
- metadata analysis;
- C2PA / Content Credentials;
- archived versions;
- cross-platform backlinks;
- domain/infrastructure relationships;
- geospatial or temporal consistency where appropriate;
- public Git history;
- source-independent corroboration.

VIGIL must preserve the distinction between:
- verified artifact;
- verified relationship;
- analyst assessment.

## 4. Separate observation from assessment

An **observation** is something directly present in a public source.

An **assessment** is an interpretation derived from one or more observations.

Examples:

- observation: two public profiles link to the same external domain;
- assessment: the profiles may be related;
- observation: a historical README explicitly links an X account and a known Instagram account;
- assessment: the X account is plausibly connected to the same public identity;
- observation: three accounts publish identical normalized text within 12 minutes;
- assessment: this is an indicator of coordination;
- observation: TinEye returns the same or modified image on another public URL;
- assessment: the visual asset was reused there.

VIGIL stores these separately.

## 5. Provenance and chain of analysis

Evidence records contain:

- source;
- collector/import adapter;
- source URL when available;
- observation time;
- reliability;
- SHA-256 content hash;
- source-specific metadata.

The hash does not prove that a web page was truthful. It proves which artifact or normalized record was used by the case.

Every derived relation should retain the evidence IDs that produced it.

The analyst audit log should make it possible to answer:

- what was collected;
- by which collector;
- when;
- what relation was derived;
- why its confidence changed;
- whether an analyst confirmed or rejected it.

## 6. Correlation

Identity correlation is deliberately conservative.

Strong signals include:

- explicit backlink to an already trusted public profile;
- a profile URL preserved in public Git history that is anchored to the seed;
- the same externally controlled domain;
- reused public media hash;
- a publication explicitly listed under a public author profile;
- independent corroboration from multiple public sources.

Weak signals include:

- similar username;
- similar display name;
- similar biography wording;
- search-engine co-occurrence.

A weak signal alone is not enough to produce an identity relation.

Different usernames are expected. Entity resolution should pivot through stable public signals, not assume username reuse.

## 7. Visual evidence

VIGIL treats visual material as evidence, not as a biometric selector.

Supported / intended signals include:

- SHA-256;
- perceptual hashes;
- EXIF/IPTC/XMP where safe;
- C2PA / Content Credentials;
- reverse-image matches;
- OCR text;
- visual reuse across public pages;
- video keyframes.

A reverse-image match means the same visual asset, or a derivative, was observed elsewhere. It does not prove that two different images depict the same person.

The project deliberately does not implement private-person facial identification.

## 8. Fake / impersonation

Impersonation scoring is multi-signal and explainable.

Signals can include:

- handle/name similarity;
- reused public visual identity;
- official-link reuse;
- suspicious divergent external domains;
- profile sparsity;
- synchronized behavior.

The analyst still owns the conclusion. The score is triage, not a verdict.

## 9. Coordinated behavior / influence-operation analysis

The defensive detector looks for measurable public behavior such as:

- identical or near-identical content;
- repeated URL sharing;
- temporal bursts;
- repeated media reuse;
- cross-platform synchronization.

A coordination finding means:
- a measurable behavioral pattern exists;
- the pattern deserves analyst review.

It does **not** prove:
- common control;
- malicious intent;
- a specific actor;
- a "psyop";
- coordinated inauthentic behavior without further evidence.

Attribution must be a separate analytical step.

## 10. Temporal reasoning

Public information changes.

VIGIL should treat:

```text
attribute + source + observed_at
```

as more meaningful than a timeless key/value field.

Examples:

- an employer in 2025 and another in 2026 are not automatically contradictory;
- a removed social link can still be historically valid;
- archived pages may describe a previous state.

Long-term, observations should support `valid_from` / `valid_to` and freshness weighting.

## 11. Source independence

Ten websites repeating the same press release are not ten independent confirmations.

Before increasing confidence, VIGIL should ask:

- are these genuinely independent sources?
- are they quoting the same upstream source?
- are they mirrors or aggregators?
- is one source simply indexing another?

Source diversity should matter more than source count.

## 12. Alternative hypotheses

Before accepting a high-impact conclusion, record at least one plausible alternative explanation.

Examples:

- same image may be licensed or reposted;
- same text may be syndicated;
- same domain may be a shared link-in-bio provider;
- similar username may be coincidence;
- synchronized publishing may be scheduled campaign content.

A good investigation tries to disprove its preferred hypothesis.

## 13. Confidence language

Suggested interpretation:

| Confidence | Meaning |
|---|---|
| < 0.35 | weak / insufficient |
| 0.35–0.64 | plausible; needs corroboration |
| 0.65–0.84 | strong multi-signal support |
| >= 0.85 | very strong support, still not absolute proof |

Confidence should reflect evidence quality and independence, not analyst enthusiasm.

## 14. Review + confirmation

Before a finding becomes reportable:

- inspect the underlying evidence;
- check whether signals are independent;
- inspect contradictions;
- review alternative hypotheses;
- mark key relations confirmed / rejected / needs-review;
- verify that confidence language matches the evidence;
- confirm that the conclusion does not exceed what the source proves.

High-impact findings should ideally have at least two independent supporting signals.

## 15. Presentation

A professional report should include:

1. objective and scope;
2. methodology;
3. key findings;
4. graph or timeline views where useful;
5. evidence ledger;
6. confidence and rationale;
7. alternative explanations;
8. collection limitations;
9. timestamps;
10. hashes / provenance information;
11. unresolved questions.

The report should distinguish:

```text
observed fact
→ derived relationship
→ analyst assessment
```

so the reader can independently evaluate the reasoning.

## Bellingcat influence

VIGIL intentionally borrows several methodological principles associated with Bellingcat-style open-source investigations:

- question-driven investigation rather than indiscriminate collection;
- collection and preservation as a formal stage;
- visual verification through multiple techniques;
- corroboration and alternative hypotheses;
- clear distinction between evidence and assessment;
- reproducible workflows;
- archiving volatile online material;
- presentation that exposes the chain from source to conclusion.

Bellingcat is a methodological reference, not a provider whose conclusions VIGIL copies automatically.
