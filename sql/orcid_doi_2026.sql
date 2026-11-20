-- One row per (iD, DOI, source), 2026 ORCID public file. Same as the NSW project.
SELECT t.orcid_identifier.path id, LOWER(TRIM(i.normalized)) doi,
  IFNULL(r.source.source_client_id.path, r.source.source_orcid.path) src, r.created_date cd, gi gidx
FROM `{{ORCID_TABLE}}` t, UNNEST(t.activities.works.groups) g WITH OFFSET gi, UNNEST(g.records) r, UNNEST(r.external_ids.identifiers) i
WHERE i.type = 'doi' AND IFNULL(i.relationship,'self') = 'self' AND i.normalized IS NOT NULL
