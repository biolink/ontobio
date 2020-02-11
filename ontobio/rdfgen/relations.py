
__relation_label_lookup = {
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
    "contributes to": "http://purl.obolibrary.org/obo/RO_0002326"
}

def lookup_label(label, default=None):
    return __relation_label_lookup.get(label.replace("_", " "), default)

def label_relation_lookup():
    return __relation_label_lookup
