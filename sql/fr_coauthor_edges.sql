-- Co-author edges among French thesis directors who have an ORCID iD (2026 public file).
-- Edge = two iDs sharing a DOI; DOIs held by >100 iDs in the whole file are excluded (as in the NSW analysis).
WITH cohort AS (SELECT DISTINCT orcid id FROM `{{BQ_PROJECT}}.{{BQ_DATASET}}.fr_director_orcid_candidates`),
size AS (SELECT doi, COUNT(DISTINCT id) n FROM `{{BQ_PROJECT}}.{{BQ_DATASET}}.orcid_doi_2026` GROUP BY doi),
c AS (
  SELECT DISTINCT d.id, d.doi FROM `{{BQ_PROJECT}}.{{BQ_DATASET}}.orcid_doi_2026` d
  JOIN size USING (doi) WHERE n <= 100 AND d.id IN (SELECT id FROM cohort)
)
SELECT x.id a, y.id b, COUNT(*) shared
FROM c x JOIN c y ON x.doi = y.doi AND x.id < y.id
GROUP BY 1, 2
