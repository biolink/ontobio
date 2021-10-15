"""
Adapter between MME API model and Monarch sim API

See https://github.com/ga4gh/mme-apis/blob/87f615/search-api.md

Original API code here: https://github.com/monarch-initiative/monarch-mme
"""
from typing import List

from ontobio.model.mme.request import MmeRequest, Observed
from ontobio.model.mme.response import MmeResponse, Result, Score
from ontobio.golr.golr_query import GolrSearchQuery
from ontobio.sim.phenosim_engine import PhenoSimEngine


def clean_feature_ids(id: str) -> str:
    """
    MME queries often need to be sanitized before going into owlsim, for example:
    MIM:610536 -> OMIM:610536
    SHH -> HGNC:10848
    """
    if ':' in id:
        prefix, reference = id.split(':')
        if prefix == 'MIM':
            id = 'OMIM:' + reference
    else:
        # Assume it's a label and look it up
        # Assume it's human, and make sure it's an exact match
        query = GolrSearchQuery(id, taxon=['NCBITaxon:9606'], min_match="100%")
        results = query.search()
        if results.docs:
            id = results.docs[0]['id']

    return id


def extract_features_from_mme(patient: MmeRequest) -> List:
    """
    Extract features or diseases and genes of interest from MME request object

    If the record contains feature(s) with is_observed=True will we will send
    those to owlsim, otherwise we will the disease(s) of interest, if there
    are no diseases, will send and gene(s) of interest to owlsim.  Essentially
    the goal is to send the smallest profile to owlsim to get the best match
    """
    features = [clean_feature_ids(feature.id) for feature in patient.features if feature.observed == Observed.yes]
    diseases = [clean_feature_ids(disease.id) for disease in patient.disorders]
    genes = [clean_feature_ids(genomic_feature.gene.id) for genomic_feature in patient.genomicFeatures]
    if features:
        return features
    elif diseases:
        return diseases
    elif genes:
        return genes


def query_owlsim(patient: MmeRequest, sim_engine: PhenoSimEngine, taxon: str = None) -> MmeResponse:
    """
    Query owlsim with features from MmeRequest object,
    see extract_features_from_mme for what features are selected to
    be sent to owlsim
    """
    features = extract_features_from_mme(patient)
    results = sim_engine.search(
            id_list=features,
            limit=100,
            taxon_filter=taxon,
            is_feature_set=False
        )
    mme_response = MmeResponse()

    for result in results.matches:
        mme_score = Score(patient=result.score)
        mme_result = Result(mme_score)
        if result.id.startswith('MONDO'):
            mme_result._disease = result.id
            mme_result._disease_label = result.label
        else:
            mme_result._gene = result.id
            mme_result._gene_label = result.label

        mme_response.results.append(mme_result)

    return mme_response
