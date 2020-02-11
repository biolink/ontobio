import json

from ontobio.io import gaference
from ontobio.model import association


def test_build_annotation_inferences():
    with open("tests/resources/test.inferences.json") as inferences_file:
        gaferences = json.load(inferences_file)
        inferences = gaference.build_annotation_inferences(gaferences)

        akey = gaference.AnnotationKey(
            gaference.RelationTo("http://purl.obolibrary.org/obo/BFO_0000050", "http://purl.obolibrary.org/obo/GO_0036064"),
            "http://purl.obolibrary.org/obo/NCBITaxon_10090",
            association.ExtensionConjunctions(frozenset([
                association.ExtensionUnit("http://purl.obolibrary.org/obo/BFO_0000050", "http://purl.obolibrary.org/obo/EMAPA_17168"),
                association.ExtensionUnit("http://purl.obolibrary.org/obo/BFO_0000050", "http://purl.obolibrary.org/obo/CL_0010009")
            ])))

        val = inferences[akey]

        expected = gaference.InferenceValue(True, False,
            [gaference.RelationTo("http://purl.obolibrary.org/obo/BFO_0000050", "http://purl.obolibrary.org/obo/GO_0097458")])

        assert val == expected


def test_produce_inference_produces_inferences():
    with open("tests/resources/test.inferences.json") as inference_file:
        gaferences = json.load(inference_file)
        inferences = gaference.build_annotation_inferences(gaferences)

    gaf_line = "MGI\tMGI:2178217\tAkap9\t\tGO:0036064\tMGI:MGI:5303017|PMID:22031837\tIDA\t\tC\tA kinase (PRKA) anchor protein (yotiao) 9\t5730481H23Rik|AKAP450|G1-448-15|mei2-5|repro12\tprotein\ttaxon:10090\t20131226\tMGI\tpart_of(EMAPA:17168),part_of(CL:0010009)\t"
    gaf = gaf_line.split("\t")

    results = gaference.produce_inferences(gaf, inferences)
    expected_line = ["MGI", "MGI:2178217", "Akap9", "", "GO:0097458", "MGI:MGI:5303017|PMID:22031837", "IDA", "", "C", "A kinase (PRKA) anchor protein (yotiao) 9", "5730481H23Rik|AKAP450|G1-448-15|mei2-5|repro12", "protein", "taxon:10090", "20131226", "MGI", "", ""]
    assert len(results) == 1
    assert len(results[0].inferred_gafs) == 1
    assert results[0].inferred_gafs[0] == expected_line

def test_produce_inference_produces_many_inferences():
    with open("tests/resources/test.inferences.json") as inference_file:
        gaferences = json.load(inference_file)
        inferences = gaference.build_annotation_inferences(gaferences)

    gaf_line = "MGI\tMGI:1345162\tAdam23\t\tGO:0099056\tMGI:MGI:4431144|PMID:20133599\tIDA\t\tC\ta disintegrin and metallopeptidase domain 23\tMDC3\tprotein\ttaxon:10090\t20180711\tSynGO\tpart_of(GO:0098978),part_of(UBERON:0000061),part_of(EMAPA:35405)|part_of(GO:0098978),part_of(UBERON:0000061),part_of(EMAPA:16894)\t"
    gaf = gaf_line.split("\t")

    results = gaference.produce_inferences(gaf, inferences)
    expected_lines = [
        ["MGI", "MGI:1345162", "Adam23", "", "GO:0098978", "MGI:MGI:4431144|PMID:20133599", "IDA", "", "C", "a disintegrin and metallopeptidase domain 23", "MDC3", "protein", "taxon:10090", "20180711", "SynGO", "", ""],
        ["MGI", "MGI:1345162", "Adam23", "", "GO:0098978", "MGI:MGI:4431144|PMID:20133599", "IDA", "", "C", "a disintegrin and metallopeptidase domain 23", "MDC3", "protein", "taxon:10090", "20180711", "SynGO", "", ""],
    ]
    assert len(results) == 2
    assert results[0].inferred_gafs[0] == expected_lines[0]
    assert results[1].inferred_gafs[0] == expected_lines[1]


def test_taxon_check_failure():
    with open("tests/resources/test.inferences.json") as inference_file:
        gaferences = json.load(inference_file)
        inferences = gaference.build_annotation_inferences(gaferences)

    gaf_line = "MGI\tMGI:1924956\tAbcb5\t\tGO:0048058\tMGI:MGI:5585659|PMID:25030174\tIMP\t\tP\tATP-binding cassette, sub-family B (MDR/TAP), member 5\t9230106F14Rik\tprotein\ttaxon:10090\t20140729\tUniProt\t\t"
    gaf = gaf_line.split("\t")

    results = gaference.produce_inferences(gaf, inferences)

    assert len(results) == 1
    assert results[0].problem == gaference.ProblemType.TAXON

def test_pombase_taxon_failure():
    with open("tests/resources/test.inferences.json") as inference_file:
        gaferences = json.load(inference_file)
        inferences = gaference.build_annotation_inferences(gaferences)

    gaf_line = "PomBase\tSPBC11B10.09\tcdc2\t\tGO:0007275\tPMID:21873635\tIBA\tPANTHER:PTN000623979|TAIR:locus:2099478\tP\tCyclin-dependent kinase 1\tUniProtKB:P04551|PTN000624043\tprotein\ttaxon:284812\t20170228\tGO_Central"
    gaf = gaf_line.split("\t")

    results = gaference.produce_inferences(gaf, inferences)

    assert len(results) == 1
    assert results[0].problem == gaference.ProblemType.TAXON

def test_extension_check_failure():
    with open("tests/resources/test.inferences.json") as inference_file:
        gaferences = json.load(inference_file)
        inferences = gaference.build_annotation_inferences(gaferences)

    gaf_line = "MGI\tMGI:109192\tActn2\t\tGO:0072659\tMGI:MGI:4366185|PMID:19815520\tIMP\t\tP\tactinin alpha 2\t1110008F24Rik\tprotein\ttaxon:10090\t20150506\tUniProt\tpart_of(CL:0002495),has_direct_input(UniProtKB:P58390)\t"
    gaf = gaf_line.split("\t")

    results = gaference.produce_inferences(gaf, inferences)

    assert len(results) == 1
    assert results[0].problem == gaference.ProblemType.EXTENSION
