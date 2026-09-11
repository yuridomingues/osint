# Case playbooks

These playbooks keep collection tied to a specific question instead of turning a case into an unbounded dossier.

## Brand impersonation

**Question:** is a public account plausibly impersonating a brand or official public identity?

1. Create a `public_account` case.
2. Import public observations from Sherlock/Maigret or the generic schema.
3. Record official public domains/links as reference observations.
4. Review account-to-domain relationships.
5. Use the impersonation assessment for triage.
6. Verify every high-confidence relation against the evidence ledger.
7. Record alternative explanations such as fan/community accounts or legitimate regional accounts.

Useful signals:

- highly similar handle/display name;
- reused public brand imagery;
- copied official links;
- suspicious divergent external domain;
- synchronized activity.

The output is an assessment, not an identity verdict.

## Coordinated influence / misinformation

**Question:** does a public dataset contain measurable signs of coordinated publishing?

1. Create a case for the dataset/campaign being studied.
2. Import public posts through `/posts`.
3. Review content clusters and their temporal spread.
4. Inspect each evidence item and original public URL.
5. Separate coordination indicators from attribution.
6. Document counter-hypotheses such as syndicated content, scheduled campaign posts or legitimate cross-posting.

The built-in detector currently requires at least three distinct accounts publishing identical normalized content inside a short time window.

## Domain / organization

**Question:** what public infrastructure relationships can be established without probing the target?

1. Create a `domain` or `organization` case with a domain as the target.
2. Run the built-in passive collection.
3. Review Certificate Transparency hostnames.
4. Review RDAP nameservers and registration metadata.
5. Review Internet Archive historical URL evidence.
6. Import additional passive outputs only when they are in the investigation's authorized organizational scope.
7. Export GraphML for deeper link analysis if needed.

## Reporting checklist

Before reporting a conclusion, verify:

- source URL and observation time;
- whether the source is primary or derivative;
- at least one alternative explanation;
- whether multiple signals are actually independent;
- whether confidence language matches the evidence;
- whether the conclusion goes beyond what the source proves.
