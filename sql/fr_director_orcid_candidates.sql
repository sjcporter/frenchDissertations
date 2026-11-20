-- ORCID candidates for French thesis directors (2005+).
--  idref : ORCID listed in the director's IdRef authority record (kept only if that iD exists in the 2026 ORCID file)
--  scopus: ORCID record whose Scopus Author ID equals a Scopus ID listed in the director's IdRef record
WITH ids AS (SELECT ppn, source, identifier FROM `{{BQ_PROJECT}}.{{BQ_DATASET}}.fr_director_ids`),
orcids AS (
  SELECT t.orcid_identifier.path orcid,
    t.person.name.given_names given, t.person.name.family_name family
  FROM `{{ORCID_TABLE}}` t
),
sc AS (
  SELECT t.orcid_identifier.path orcid, REGEXP_EXTRACT(i.value, r'(\d{6,})') scopus
  FROM `{{ORCID_TABLE}}` t, UNNEST(t.person.external_identifiers.identifiers) i
  WHERE LOWER(i.type) LIKE '%scopus%'
)
SELECT ppn, orcid, 'idref' via, o.given, o.family FROM (
  SELECT ppn, REGEXP_EXTRACT(identifier, r'(\d{4}-\d{4}-\d{4}-\d{3}[\dX])') orcid FROM ids WHERE source = 'ORCID'
) JOIN orcids o USING (orcid)
UNION ALL
SELECT i.ppn, s.orcid, 'scopus', o.given, o.family
FROM ids i JOIN sc s ON s.scopus = REGEXP_EXTRACT(i.identifier, r'(\d{6,})') JOIN orcids o ON o.orcid = s.orcid
WHERE i.source = 'SCOPUSID'
