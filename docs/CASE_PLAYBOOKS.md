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


## Visual evidence / reverse-image investigation

**Question:** where else has this visual asset appeared, and what public context can be verified around those appearances?

1. Preserve and hash the original file before transformation.
2. Extract safe metadata and record whether C2PA/Content Credentials are present.
3. Compute perceptual hashes for local corpus matching.
4. Run one or more reverse-image providers when configured.
5. Preserve every matched public URL as evidence.
6. Separate "same/modified image" from any claim about who appears in it.
7. Pivot from matched pages to public accounts, publications, domains or archived copies.
8. Compare timestamps and find the earliest verifiable public occurrence.
9. Record alternative explanations such as licensed/reposted media.
10. Report unresolved provenance instead of forcing attribution.

This playbook follows the verification-first logic common in Bellingcat visual investigations: identify the artifact, preserve it, verify its provenance/context, corroborate, then present.

## Source preservation playbook

**Question:** can this source still be independently reviewed if the page changes or disappears?

For important public URLs:

1. record the original URL;
2. record redirects and observation time;
3. preserve page/media bytes when lawful and technically possible;
4. calculate SHA-256;
5. create a screenshot or rendered representation;
6. archive through an external preservation service or VIGIL's future archive worker;
7. record collector version and archive identifier;
8. keep original artifact and derived representations separate.

The design target is similar to Bellingcat's Auto Archiver philosophy: collection should produce both preserved content and metadata that helps demonstrate integrity.
