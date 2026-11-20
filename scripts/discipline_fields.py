#!/usr/bin/env python3
"""Map fine-grained theses.fr discipline labels to broad fields coded like ANZSRC FOR divisions.

The UniversityExplorer Blender template colours, orders and stacks clusters by a two-digit
FOR code (the 19 divisions in FOR1_ORDER). Reusing those codes lets the unchanged template
work on the French supervision network. Law folds into 44 (Human Society), philosophy,
religion and the arts into 47 (Language, Communication and Culture), because the template
legend has no slots for 48, 50 or 36.
"""
from __future__ import annotations

import re
import unicodedata

FIELD_NAMES: dict[str, str] = {
    "32": "Biomedical and Clinical Sciences", "42": "Health Sciences", "52": "Psychology",
    "31": "Biological Sciences", "30": "Agricultural, Veterinary and Food Sciences",
    "41": "Environmental Sciences", "34": "Chemical Sciences", "51": "Physical Sciences",
    "49": "Mathematical Sciences", "46": "Information and Computing Sciences", "40": "Engineering",
    "33": "Built Environment and Design", "37": "Earth Sciences", "43": "History, Heritage and Archaeology",
    "38": "Economics", "35": "Commerce, Management and Services", "44": "Human Society (incl. law)",
    "39": "Education", "47": "Language, Communication and Culture",
}

# first match wins; patterns run on lower-case, accent-stripped labels
RULES: list[tuple[str, str]] = [
    (r"sciences? de l.information et de la communication", "47"),
    (r"technologies? de l.information|signal|image|telecom|informati|intelligence artificielle|robotique|reseaux?\b|cybern|calcul|data|logiciel|numerique", "46"),
    (r"archeo|prehistoire", "43"),
    (r"materiaux, mecanique, genie civil", "40"),
    (r"chimie physique|physico.?chim|physicochim", "34"),
    (r"neuroscien|immunolog|cancer|oncolog|medecin|medical|patholog|cardio|infectieu|virolog|therap|biomedic|toxicolog|physiolog|endocrin|neurolog|psychiatr|pharma|genetique humaine|biologie.sante|sciences de la vie et de la sante|chirurg|imagerie|odonto|dentaire|sciences cliniques|hematolog|oncogen|infectiolog|medicament|recherche clinique", "32"),
    (r"epidemiolog|sante publique|activites physiques|sciences du sport|\bstaps\b|infirm|soins|nutrition|ergonom|sante|reeducation|mouvement humain", "42"),
    (r"psycholog|sciences cognitives|cognition|psychanalys", "52"),
    (r"agronom|agricol|veterin|aliment|foresterie|horticol|production animale|viticul|oenolog|agro|sciences du sol|sciences de l.aliment|zootechn", "30"),
    (r"environnement|climat|ocean|hydrolog|ressources en eau|developpement durable|ecotox|pollution|ecosyst", "41"),
    (r"chim|catalyse|polymere|electrochim|spectro", "34"),
    (r"physi|astro|optique|photon|plasma|particule|matiere condensee|laser|cosmolog|quantique|nanophys|nucleaire", "51"),
    (r"mathemat|statistique|probabilit|algebre|analyse num|geometrie|topolog|combinatoire|optimisation", "49"),
    (r"genie|mecanique|electronique|electrique|automatique|procedes|materiaux|ingenieur|energetique|aeronaut|fluides|thermique|acoustique|microelectron|microsystem|micro-onde|microfluid|micromec|nano|structures|combustion|hydraulique|metallurg|soudage|mecatronique|systemes|industrielles|conception|bois", "40"),
    (r"architecture|urbanisme|amenagement|paysage|design|genie urbain", "33"),
    (r"geoscien|sciences de la terre|geolog|geophys|geochim|univers|atmosph|sismolog|mineralog|geodesie|planetolog|paleontolog|terre|geotechn|geomatique|volcanolog", "37"),
    (r"biolog|ecolog|genetique|biochim|microbiolog|evolution|botanique|zoolog|biodiversit|sciences de la vie|moleculaire|cellulaire|biophys|bioinform|vegetal|genomi|ethologie|parasitolog|entomolog|biotechnolog|vivant", "31"),
    (r"histoire de l.art|musicolog|cinema|arts du spectacle|sciences de l.art|arts plastiques|\barts?\b|theatre|esthetique", "47"),
    (r"histoire|archeolog|prehistoire|archeozoolog|patrimoine|antiquit|egyptolog|etudes anciennes|paleograph|numismat", "43"),
    (r"economi|econometri|finance|monnaie", "38"),
    (r"gestion|management|marketing|comptab|organisation|tourisme|logistique|ressources humaines|entrepreneuriat|commerce|affaires", "35"),
    (r"education|didactique|pedagogi|formation|enseignement", "39"),
    (r"droit|juridi|sociolog|anthropolog|geographie|politique|relations internationales|demograph|ethnolog|etudes urbaines|sciences sociales|criminolog|sciences humaines|service social|science administrative", "44"),
    (r"langue|litterature|linguistique|langage|etudes|philosoph|theolog|religio|communication|traduction|lettres|civilisation|culture|sciences de l.information|medias|semiolog|archivistique|bibliotheconomie|anglais|espagnol|musique|arabe|religieuses|allemand|italien", "47"),
]
_COMPILED = [(re.compile(p), code) for p, code in RULES]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def field_of(discipline: str) -> str:
    """Return a FOR-style code, or '' if no rule matches."""
    d = norm(discipline)
    for rx, code in _COMPILED:
        if rx.search(d):
            return code
    return ""
