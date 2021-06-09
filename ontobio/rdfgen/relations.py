from bidict import bidict
from ontobio.model import association


def obo_uri_to_curie(uri: str):

    """
    OBO URIs and CURIEs follow the same pattern: <base>/<namespace>_<local_id>

    So this just looks at the last slash separated item, splits on underscore, and we have our Curie.
    """
    full_identifier = uri.rsplit("/", maxsplit=1)[1] # Throw away the base, grab the second element
    namespace, identifier = full_identifier.split("_", maxsplit=1) # Assume 1 underscore
    return association.Curie(namespace, identifier)

def curie_to_obo_uri(curie, base=None) -> str:
    """
    :param curie: association.Curie to be expanded into a URI
    :return: the expanded URI for the given CURIE
    """
    if base is None:
        base = "http://purl.obolibrary.org/obo"

    return "{base}/{ns}_{id}".format(base=base, ns=curie.namespace, id=curie.identity)


__relation_label_lookup = bidict({
    "occurs in": "http://purl.obolibrary.org/obo/BFO_0000066",
    "happens during": "http://purl.obolibrary.org/obo/RO_0002092",
    "has input": "http://purl.obolibrary.org/obo/RO_0002233",
    "results in specification of": "http://purl.obolibrary.org/obo/RO_0002356",
    "part of": "http://purl.obolibrary.org/obo/BFO_0000050",
    "has part": "http://purl.obolibrary.org/obo/BFO_0000051",
    "results in development of": "http://purl.obolibrary.org/obo/RO_0002296",
    "results in movement of": "http://purl.obolibrary.org/obo/RO_0002565",
    "occurs at": "http://purl.obolibrary.org/obo/GOREL_0000501",
    "stabilizes": "http://purl.obolibrary.org/obo/GOREL_0000018",
    "positively regulates": "http://purl.obolibrary.org/obo/RO_0002213",
    "regulates transport of": "http://purl.obolibrary.org/obo/RO_0002011",
    "regulates transcription of": "http://purl.obolibrary.org/obo/GOREL_0098788",
    "causally upstream of": "http://purl.obolibrary.org/obo/RO_0002411",
    "regulates activity of": "http://purl.obolibrary.org/obo/GOREL_0098702",
    "adjacent to": "http://purl.obolibrary.org/obo/RO_0002220",
    "results in acquisition of features of": "http://purl.obolibrary.org/obo/RO_0002315",
    "results in morphogenesis of": "http://purl.obolibrary.org/obo/RO_0002298",
    "results in maturation of": "http://purl.obolibrary.org/obo/RO_0002299",
    "has participant": "http://purl.obolibrary.org/obo/RO_0000057",
    "transports or maintains localization of": "http://purl.obolibrary.org/obo/RO_0002313",
    "negatively regulates": "http://purl.obolibrary.org/obo/RO_0002212",
    "regulates": "http://purl.obolibrary.org/obo/RO_0002211",
    "regulates expression of": "http://purl.obolibrary.org/obo/GOREL_0098789",
    "has target end location": "http://purl.obolibrary.org/obo/RO_0002339",
    "produced by": "http://purl.obolibrary.org/obo/RO_0003001",
    "has end location": "http://purl.obolibrary.org/obo/RO_0002232",
    "directly positively regulates": "http://purl.obolibrary.org/obo/RO_0002629",
    "has direct input": "http://purl.obolibrary.org/obo/GOREL_0000752",
    "enables": "http://purl.obolibrary.org/obo/RO_0002327",
    "enabled by": "http://purl.obolibrary.org/obo/RO_0002333",
    "involved in": "http://purl.obolibrary.org/obo/RO_0002331",
    "acts upstream of": "http://purl.obolibrary.org/obo/RO_0002263",
    "colocalizes with": "http://purl.obolibrary.org/obo/RO_0002325",
    "contributes to": "http://purl.obolibrary.org/obo/RO_0002326",
    "acts upstream of or within": "http://purl.obolibrary.org/obo/RO_0002264",
    "acts upstream of or within positive effect": "http://purl.obolibrary.org/obo/RO_0004032",
    "acts upstream of or within negative effect": "http://purl.obolibrary.org/obo/RO_0004033",
    "acts upstream of negative effect": "http://purl.obolibrary.org/obo/RO_0004035",
    "acts upstream of positive effect": "http://purl.obolibrary.org/obo/RO_0004034",
    "located in": "http://purl.obolibrary.org/obo/RO_0001025",
    "is active in": "http://purl.obolibrary.org/obo/RO_0002432",
    "exists during": "http://purl.obolibrary.org/obo/RO_0002491",
    "coincident with": "http://purl.obolibrary.org/obo/RO_0002008",
    "has regulation target": "http://purl.obolibrary.org/obo/GOREL_0000015",
    "not happens during": "http://purl.obolibrary.org/obo/GOREL_0000025",
    "not exists during": "http://purl.obolibrary.org/obo/GOREL_0000026",
    "directly negatively regulates": "http://purl.obolibrary.org/obo/RO_0002449",
    "inhibited by": "http://purl.obolibrary.org/obo/GOREL_0000508",
    "activated by": "http://purl.obolibrary.org/obo/GOREL_0000507",
    "regulates o acts on population of": "http://purl.obolibrary.org/obo/GOREL_0001008",
    "regulates o occurs in": "http://purl.obolibrary.org/obo/GOREL_0001004",
    "regulates o results in movement of": "http://purl.obolibrary.org/obo/GOREL_0001005",
    "acts on population of": "http://purl.obolibrary.org/obo/RO_0012003",
    "regulates o has input": "http://purl.obolibrary.org/obo/GOREL_0001030",
    "regulates o has participant": "http://purl.obolibrary.org/obo/GOREL_0001016",
    "has output o axis of": "http://purl.obolibrary.org/obo/GOREL_0001002",
    "regulates o results in formation of": "http://purl.obolibrary.org/obo/GOREL_0001025",
    "regulates o results in acquisition of features of": "http://purl.obolibrary.org/obo/GOREL_0001010",
    "regulates o has agent": "http://purl.obolibrary.org/obo/GOREL_0001011",
    "results in formation of": "http://purl.obolibrary.org/obo/RO_0002297",
    "has start location": "http://purl.obolibrary.org/obo/RO_0002231",
    "has output": "http://purl.obolibrary.org/obo/RO_0002234",
    "results in commitment to": "http://purl.obolibrary.org/obo/RO_0002348",
    "regulates o results in commitment to": "http://purl.obolibrary.org/obo/GOREL_0001022",
    "regulates o has output": "http://purl.obolibrary.org/obo/GOREL_0001003",
    "regulates o results in development of": "http://purl.obolibrary.org/obo/GOREL_0001023",
    "results in determination of": "http://purl.obolibrary.org/obo/RO_0002349",
    "regulates o results in maturation of": "http://purl.obolibrary.org/obo/GOREL_0001012",
    "regulates o results in morphogenesis of": "http://purl.obolibrary.org/obo/GOREL_0001026",
    "has agent": "http://purl.obolibrary.org/obo/RO_0002218",
    "causally upstream of or within": "http://purl.obolibrary.org/obo/RO_0002418",
    "overlaps": "http://purl.obolibrary.org/obo/RO_0002131",
    "has target start location": "http://purl.obolibrary.org/obo/RO_0002338",
    "capable of part of": "http://purl.obolibrary.org/obo/RO_0002216",
    "regulates o results in specification of": "http://purl.obolibrary.org/obo/GOREL_0001027",
    "results in division of": "http://purl.obolibrary.org/obo/GOREL_0001019",
    "regulates translation of": "http://purl.obolibrary.org/obo/GOREL_0098790",
    "imports": "http://purl.obolibrary.org/obo/RO_0002340",
    "directly regulates": "http://purl.obolibrary.org/obo/RO_0002578",
    "regulates o results in division of": "http://purl.obolibrary.org/obo/GOREL_0001024",
    "regulates o transports or maintains localization of": "http://purl.obolibrary.org/obo/GOREL_0000038",
    "starts": "http://purl.obolibrary.org/obo/RO_0002223",
    "starts with": "http://purl.obolibrary.org/obo/RO_0002224",
    "ends": "http://purl.obolibrary.org/obo/RO_0002229",
    "ends with": "http://purl.obolibrary.org/obo/RO_0002230",
    "involved in regulation of": "http://purl.obolibrary.org/obo/RO_0002428",
    "involved in positive regulation of": "http://purl.obolibrary.org/obo/RO_0002429",
    "involved in negative regulation of": "http://purl.obolibrary.org/obo/RO_0002430"
})

def lookup_uri(uri, default=None):
    if uri is None:
        return default

    return __relation_label_lookup.inverse.get(uri, default).replace(" ", "_")

def lookup_label(label, default=None):
    if label is None:
        return default

    return __relation_label_lookup.get(label.replace("_", " "), default)

def label_relation_lookup():
    return __relation_label_lookup
