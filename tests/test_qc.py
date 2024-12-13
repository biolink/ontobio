import pytest
import datetime
import yaml

from ontobio.model import association
from ontobio.model.association import Curie
from ontobio.io.gpadparser import GpadParser
from ontobio.io import qc
from ontobio.io import gaference
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio.io.gafparser import GafParser
from ontobio.io import gpadparser
from ontobio import ontol_factory, ecomap

import copy

ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")
ontology_obsolete = ontol_factory.OntologyFactory().create("tests/resources/obsolete.json")
ecomapping = ecomap.EcoMap()
iea_eco = ecomapping.coderef_to_ecoclass("IEA")
hep_eco = ecomapping.coderef_to_ecoclass("HEP")
ic_eco = ecomapping.coderef_to_ecoclass("IC")
ikr_eco = ecomapping.coderef_to_ecoclass("IKR")
iba_eco = ecomapping.coderef_to_ecoclass("IBA")
iso_eco = ecomapping.coderef_to_ecoclass("ISO")




def make_annotation(db="blah",
                    db_id="blah12345",
                    db_obj_symb="blah",
                    qualifier="",
                    negated=False,
                    goid="GO:1234567",
                    references="BLAH:54321",
                    evidence="IDA",
                    withfrom="BLAH:12345",
                    aspect="C",
                    db_obj_name="",
                    db_obj_syn="",
                    db_obj_type="blah",
                    taxon="taxon:12345",
                    date="20200330",
                    assigned_by="blah",
                    extension="",
                    gene_form_id="",
                    properties="",
                    version=None,
                    from_gaf=True):

    if from_gaf:
        qual_parse = assocparser.Qualifier2_1()
        if version == "2.2":
            qual_parse = assocparser.Qualifier2_2()

        annotation = [db, db_id, db_obj_symb, qualifier, goid, references, evidence, withfrom, aspect, db_obj_name, db_obj_syn, db_obj_type, taxon, date, assigned_by, extension, gene_form_id]

        return gafparser.to_association(annotation, qualifier_parser=qual_parse)
    else:
        if version != "2.0":
            # Default to 1.2 if we're anything but 2.0
            annotation = [db, db_id, qualifier, goid, references, evidence, withfrom, taxon, date, assigned_by, extension, properties]
            return gpadparser.to_association(annotation, version="1.2")
        else:
            annotation = ["{}:{}".format(db, db_id), "NOT" if negated else "", qualifier, goid, references, evidence, withfrom, taxon, date, assigned_by, extension, properties]
            return gpadparser.to_association(annotation, version="2.0")

def all_rules_config(ontology=None) -> assocparser.AssocParserConfig:
    return assocparser.AssocParserConfig(
        ontology=ontology,
        rule_set=assocparser.RuleSet.ALL
    )

def test_qc_result():
    assert qc.result(True, qc.FailMode.HARD) == qc.ResultType.PASS
    assert qc.result(False, qc.FailMode.HARD) == qc.ResultType.ERROR
    assert qc.result(False, qc.FailMode.SOFT) == qc.ResultType.WARNING

def test_go_rule02():

    assoc = make_annotation(qualifier="NOT", goid="GO:0005515").associations[0]

    test_result = qc.GoRule02().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.negated = False
    test_result = qc.GoRule02().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.negated = True
    assoc.object.id = Curie.from_str("GO:0003674")
    test_result = qc.GoRule02().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS
    
def test_go_rule_05():
    fail_terms = ["GO:0005488", "GO:0005515"]
    fail_codes = ["IEA", "ISS", "ISO", "ISM", "ISA", "IBA", "RCA"]
    for term in fail_terms:
        for code in fail_codes:
            assoc = make_annotation(goid=term, evidence=code).associations[0]
            test_result = qc.GoRule05().test(assoc, all_rules_config(ontology=ontology))
            assert test_result.result_type == qc.ResultType.WARNING
    
    assoc = make_annotation(goid="GO:0034655", evidence="IEA").associations[0]
    test_result = qc.GoRule05().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS
    
    
    assoc = make_annotation(goid="GO:0005488", evidence="HEP").associations[0]
    test_result = qc.GoRule05().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS
    
    assoc = make_annotation(goid="GO:0034655", evidence="HEP").associations[0]
    test_result = qc.GoRule05().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS    
    
def test_go_rule_06():

    assoc = make_annotation(goid="GO:0005575", evidence="HEP", aspect="C").associations[0]

    test_result = qc.GoRule06().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.aspect = "P"
    assoc.object.id = Curie.from_str("GO:0008150")
    test_result = qc.GoRule06().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = Curie.from_str(iea_eco)
    test_result = qc.GoRule06().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS
    
    assoc.evidence.type = Curie.from_str(hep_eco)
    assoc.provided_by = "GOC"
    assoc.aspect = "F"
    assoc.object.id = Curie.from_str("GO:0003674");    
    test_result = qc.GoRule06().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS    

    assoc.provided_by = "WB"  
    test_result = qc.GoRule06().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.ERROR
    
    #Ensure obsoleted GO id is repaired with alternate id first before Gorule06
    line = ["GeneDB", "PF3D7_0507500", "SUB1", "enables", "GO:0006758", "PMID:12764150", "IEP", "PANTHER:PTN000623979|TAIR:locus:2099478", "C", "GORULE:0000006-6", "protease 1", "gene", "NCBITaxon:36329", "20090624", "GeneDB", "", ""]
    obs_ontology = ontol_factory.OntologyFactory().create("tests/resources/obsolete.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=obs_ontology, rule_set = assocparser.RuleSet.ALL))
    p.version = "2.2"
    parsed = p.parse_line("\t".join(line))
    assoc = parsed.associations[0]
    assert assoc.object.id == Curie.from_str("GO:0006754")
    test_result = qc.GoRule06().test(assoc, all_rules_config(ontology=obs_ontology))
    assert test_result.result_type == qc.ResultType.PASS
    
def test_go_rule_07():

    assoc = make_annotation(goid="GO:0003824", evidence="IPI").associations[0]

    test_result = qc.GoRule07().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.object.id = Curie.from_str("GO:1234567")
    test_result = qc.GoRule07().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = Curie.from_str("GO:0003824")
    assoc.evidence.type = iea_eco # Not IPI
    test_result = qc.GoRule07().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule08():

    assoc = make_annotation(goid="GO:0006810", evidence="IEA").associations[0]

    test_result = qc.GoRule08().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.type = Curie.from_str(ic_eco)
    test_result = qc.GoRule08().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.object.id = Curie.from_str("GO:0007049")  # do not manually annotate
    # evidence is IC, non IEA
    test_result = qc.GoRule08().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.type = Curie.from_str(iea_eco) #IEA
    # IEA, but on not manual, so should pass
    test_result = qc.GoRule08().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = Curie.from_str("GO:0034655")  # neither
    assoc.evidence.type = Curie.from_str(ic_eco)
    test_result = qc.GoRule08().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule11():

    assoc = make_annotation(goid="GO:0003674", evidence="ND").associations[0]
    test_result = qc.GoRule11().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    # Bad GO ID
    assoc = make_annotation(goid="GO:1234567", evidence="ND").associations[0]
    test_result = qc.GoRule11().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

    # Not ND and not Root
    assoc = make_annotation(goid="GO:1234567", evidence="IEA").associations[0]
    test_result = qc.GoRule11().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    # Root, but not ND
    assoc = make_annotation(goid="GO:0003674", evidence="IEA").associations[0]
    test_result = qc.GoRule11().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

def test_go_rules_13():

    a = ["PomBase", "SPBC11B10.09", "cdc2", "", "GO:0007275", "PMID:21873635", "IBA", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    assoc = gafparser.to_association(a).associations[0]
    gaferences = gaference.load_gaferencer_inferences_from_file("tests/resources/test.inferences.json")
    test_result = qc.GoRule13().test(assoc, assocparser.AssocParserConfig(annotation_inferences=gaferences, rule_set=assocparser.RuleSet.ALL))
    assert test_result.result_type == qc.ResultType.ERROR

    a = ["PomBase", "SPBC11B10.09", "cdc2", "", "GO:0007275", "PMID:21873635", "EXP", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    assoc = gafparser.to_association(a).associations[0]
    gaferences = gaference.load_gaferencer_inferences_from_file("tests/resources/test.inferences.json")
    test_result = qc.GoRule13().test(assoc, assocparser.AssocParserConfig(annotation_inferences=gaferences, rule_set=assocparser.RuleSet.ALL))
    assert test_result.result_type == qc.ResultType.WARNING

    a = ["PomBase", "SPBC11B10.09", "cdc2", "NOT", "GO:0007275", "PMID:21873635", "EXP", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    assoc = gafparser.to_association(a).associations[0]
    gaferences = gaference.load_gaferencer_inferences_from_file("tests/resources/test.inferences.json")
    test_result = qc.GoRule13().test(assoc, assocparser.AssocParserConfig(annotation_inferences=gaferences, rule_set=assocparser.RuleSet.ALL))
    assert test_result.result_type == qc.ResultType.PASS

    a = ["AspGD", "ASPL0000059928", "AN0127", "", "GO:0032258", "AspGD_REF:ASPL0000000005", "IEA", "SGD:S000001917", "P", "", "AN0127|ANID_00127|ANIA_00127", "gene_product", "taxon:227321", "20200201", "AspGD", "", ""]
    assoc = gafparser.to_association(a).associations[0]
    gaferences = gaference.load_gaferencer_inferences_from_file("tests/resources/test.inferences.json")
    test_result = qc.GoRule13().test(assoc, assocparser.AssocParserConfig(annotation_inferences=gaferences, rule_set=assocparser.RuleSet.ALL))
    assert test_result.result_type == qc.ResultType.ERROR

def test_go_rules_15():

    assoc = make_annotation(goid="GO:0044419", taxon="taxon:123|taxon:456").associations[0]

    ontology = ontol_factory.OntologyFactory().create("tests/resources/go-interspecies-20210520.json")

    test_result = qc.GoRule15().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = Curie.from_str("GO:1234567")
    test_result = qc.GoRule15().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.object.id = Curie.from_str("GO:0002812")
    test_result = qc.GoRule15().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = Curie.from_str("GO:0044215")
    assoc.object.taxon = Curie.from_str("NCBITaxon:123")
    assoc.interacting_taxon = None # This is the important part, no interacting taxon
    test_result = qc.GoRule15().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS
    
    assoc.object.id = Curie.from_str("GO:0044419")
    assoc.interacting_taxon = Curie.from_str("NCBITaxon:123") # Taxon and interacting taxon are same
    test_result = qc.GoRule15().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING    

def test_go_rule_16():
    # GO term same as with/ID
    assoc = make_annotation(goid="GO:0044419", evidence="IC", withfrom="GO:0044419").associations[0]

    test_result = qc.GoRule16().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING
    
    #GO term same as one of the withfrom terms
    assoc = make_annotation(goid="GO:0044419", evidence="IC", withfrom="GO:0044419|GO:0035821").associations[0]
    test_result = qc.GoRule16().test(assoc, all_rules_config())    
    assert test_result.result_type == qc.ResultType.PASS    
    
    #withfrom is obsolete
    obs_config = config=assocparser.AssocParserConfig(ontology=ontology_obsolete,rule_set=assocparser.RuleSet.ALL)
    parser = GpadParser(obs_config)
    gpadLine = "MGI\tMGI:1916040\tlocated_in\tGO:0005634\tPMID:23369715\tECO:0000305\tGO:0016458\t\t20200518\tMGI\t\tcontributor=https://orcid.org/0000-0001-7476-6306|noctua-model-id=gomodel:MGI_MGI_1916040|contributor=https://orcid.org/0000-0003-2689-5511|model-state=production"
    result = parser.parse_line(gpadLine)
    assert result.associations == []        
            
    # No GO term w/ID
    assoc = make_annotation(evidence="IC", withfrom="BLAH:12345").associations[0]

    test_result = qc.GoRule16().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    # withfrom has GO term
    assoc.evidence.with_support_from = association.ConjunctiveSet.str_to_conjunctions("GO:0023456")

    test_result = qc.GoRule16().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    # Pipe
    assoc.evidence.with_support_from = association.ConjunctiveSet.str_to_conjunctions("GO:0012345|BLAH:54321")

    test_result = qc.GoRule16().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    # Empty withfrom
    assoc.evidence.with_support_from = []

    test_result = qc.GoRule16().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    # Not IC
    assoc.evidence.type = Curie.from_str(iea_eco)
    assoc.evidence.with_support_from = association.ConjunctiveSet.str_to_conjunctions("BLAH:5555555|FOO:999999")

    test_result = qc.GoRule16().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS


def test_go_rule_17():
    # IDA with anything in withfrom
    assoc = make_annotation(evidence="IDA", withfrom="BLAH:12345").associations[0]

    test_result = qc.GoRule17().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    # Nothing in withfrom, passes
    assoc.evidence.with_support_from = []
    test_result = qc.GoRule17().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_18():
    # IDA with nothing in withfrom
    a = ["blah"] * 15
    a[3] = ""
    a[5] = "PMID:12345"
    a[6] = "IPI"
    a[7] = ""
    a[8] = "P"
    a[12] = "taxon:123"
    a[13] = "20200303"
    assoc = make_annotation(evidence="IPI", withfrom="").associations[0]

    test_result = qc.GoRule18().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    # Something in withfrom, passes
    assoc.evidence.with_support_from = association.ConjunctiveSet.str_to_conjunctions("BLAH:12345")
    test_result = qc.GoRule18().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule22():
    config = assocparser.AssocParserConfig(
        ontology=ontology,
        retracted_pub_set={"RETRACTED:1234","PMID:37772366"},
        rule_set=assocparser.RuleSet.ALL
    )
    assoc = make_annotation(goid="GO:1234567", evidence="IBA", references="PMID:12345").associations[0]   
    test_result = qc.GoRule22().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS
    
    assoc = make_annotation(goid="GO:1234567", evidence="IBA", references="PMID:37772366").associations[0]   
    test_result = qc.GoRule22().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR    

def test_go_rule26():

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=True,
        rule_set=assocparser.RuleSet.ALL
    )
    assoc = make_annotation(goid="GO:1234567", evidence="IBA").associations[0]
    # Pass due to IBA in paint
    test_result = qc.GoRule26().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=False,
        rule_set=assocparser.RuleSet.ALL
    )
    assoc = make_annotation(goid="GO:1234567", evidence="IPI").associations[0]
    # Pass due to non IBA
    test_result = qc.GoRule26().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=False,
        rule_set=assocparser.RuleSet.ALL
    )
    assoc = make_annotation(goid="GO:1234567", evidence="IBA").associations[0]
    # Fail  due to non paint
    test_result = qc.GoRule26().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR

def test_go_rule28():

    config = all_rules_config(ontology=ontology)

    assoc = make_annotation(goid="GO:0005975", evidence="IDA", aspect="P").associations[0]
    test_result = qc.GoRule28().test(assoc, config)

    assert test_result.result_type == qc.ResultType.PASS
    assert test_result.result == assoc

    assoc = make_annotation(goid="GO:0005975", evidence="IDA", aspect="C").associations[0]
    test_result = qc.GoRule28().test(assoc, config)

    assert test_result.result_type == qc.ResultType.WARNING
    fixed_assoc = copy.deepcopy(assoc)
    fixed_assoc.aspect = "P"
    assert test_result.result == fixed_assoc
    assert test_result.message == "Found violation of: `Aspect can only be one of C, P, F` but was repaired"

def test_go_rule29():

    # Nov 11, 1990, more than a year old
    assoc = make_annotation(evidence="IEA", date="19901111").associations[0]

    ## Base test: old IEA.
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

    ## Pass if not IEA
    assoc.evidence.type = Curie.from_str(ic_eco)  # Not IEA
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    ## Pass if only a half year old.
    now = datetime.datetime.now()
    six_months_ago = now - datetime.timedelta(days=180)
    assoc.date = association.Date(six_months_ago.year, six_months_ago.month, six_months_ago.day, "")
    assoc.evidence.type = Curie.from_str(iea_eco)
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    ## Warning if a year and a half year old.
    eighteen_months_ago = now - datetime.timedelta(days=(30*18))
    assoc.date = association.Date(eighteen_months_ago.year, eighteen_months_ago.month, eighteen_months_ago.day, "")
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    ## Warning if two and a half years old.
    thirty_months_ago = now - datetime.timedelta(days=(30 * 30))
    assoc.date = association.Date(thirty_months_ago.year, thirty_months_ago.month, thirty_months_ago.day, "")
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    ## Error if three and a half years old.
    forty_two_months_ago = now - datetime.timedelta(days=(30 * 42))
    assoc.date = association.Date(forty_two_months_ago.year, forty_two_months_ago.month, forty_two_months_ago.day, "")
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

    ## Confirm the test can parse a YYYY-MM-DD date format from GPAD 2.0
    gpad_2_0_vals = assoc.to_gpad_2_0_tsv()  # Cheat to shortcut DB and DB_Object_ID concatenation
    gpad_2_0_vals[5] = iea_eco
    gpad_2_0_vals[8] = "1990-11-11"
    assoc = gpadparser.to_association(gpad_2_0_vals, version="2.0").associations[0]
    test_result = qc.GoRule29().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule30():
    assoc = make_annotation(references="GO_REF:0000033").associations[0]

    config = assocparser.AssocParserConfig(
        goref_metadata={
            "goref-0000033": {
                "authors": "Pascale Gaudet, Michael Livstone, Paul Thomas, The Reference Genome Project",
                "id": "GO_REF:0000033",
                "is_obsolete": True
            }
        },
        rule_set=assocparser.RuleSet.ALL
    )

    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.has_supporting_reference = [Curie.from_str("GO_PAINT:0000000")]
    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.has_supporting_reference = [Curie.from_str("FOO:123"), Curie.from_str("GO_REF:0000033")]
    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.has_supporting_reference = [Curie.from_str("FOO:123")]
    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule37():
    assoc = make_annotation(evidence="IBA", references="GO_REF:0000033", assigned_by="GO_Central").associations[0]

    test_result = qc.GoRule37().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = Curie.from_str(ic_eco) # Rule doesn't apply, not IBA
    test_result = qc.GoRule37().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = Curie.from_str(iba_eco)
    assoc.evidence.has_supporting_reference = [Curie.from_str("GO_REF:123")]  # IBA, but wrong ref
    test_result = qc.GoRule37().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.evidence.has_supporting_reference = [Curie.from_str("GO_REF:0000033")]
    assoc.provided_by = "Pascale"  # IBA, but wrong assigned_by
    test_result = qc.GoRule37().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule39():
    config = all_rules_config(ontology=ontology)
    assoc = make_annotation(db="ComplexPortal", goid="GO:0032991").associations[0]

    test_result = qc.GoRule39().test(assoc,  config)
    assert test_result.result_type == qc.ResultType.ERROR

    # test descendant of GO:0032991
    assoc = make_annotation(db="bla", goid="GO:0005840").associations[0]
    assoc.subject.type = [association.map_gp_type_label_to_curie("protein_complex")]  
    test_result = qc.GoRule39().test(assoc,  config)
    assert test_result.result_type == qc.ResultType.ERROR    
    
    # test protein complex
    assoc = make_annotation(db="bla", goid="GO:0032991").associations[0]
    assoc.subject.type= [association.map_gp_type_label_to_curie("protein_complex")]
    test_result = qc.GoRule39().test(assoc,  config)
    assert test_result.result_type == qc.ResultType.ERROR   
    
    assoc.subject.id = association.Curie("FB", "1234")
    assoc.subject.type = [association.Curie("CHEBI", "33695")]
    assoc.object.id = association.Curie("GO", "0032991")       
    test_result = qc.GoRule39().test(assoc,  config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.subject.id = association.Curie("ComplexPortal", "12345")
    assoc.object.id = association.Curie("GO", "0000023")
    test_result = qc.GoRule39().test(assoc,  config)
    assert test_result.result_type == qc.ResultType.PASS
    
    #test actual GAF file
    

def test_gorule42():
    assoc = make_annotation(qualifier="NOT", evidence="IKR").associations[0]

    test_result = qc.GoRule42().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = ic_eco # Not IKR so this rule is fine
    test_result = qc.GoRule42().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = ikr_eco
    assoc.negated = False  # Not negated, so wrong
    test_result = qc.GoRule42().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule43():
    assoc = make_annotation(references="GO_REF:0000024", evidence="ISO").associations[0]

    config = assocparser.AssocParserConfig(
        goref_metadata={
            "goref-0000024": {
                "authors": "Pascale Gaudet, Michael Livstone, Paul Thomas, The Reference Genome Project",
                "id": "GO_REF:0000024",
                "evidence_codes": [iso_eco]
            }
        },
        rule_set=assocparser.RuleSet.ALL
    )

    test_result = qc.GoRule43().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = Curie.from_str(iea_eco)
    test_result = qc.GoRule43().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.type = Curie.from_str(iso_eco)
    assoc.evidence.has_supporting_reference = [Curie.from_str("FOO:123")]
    test_result = qc.GoRule43().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule46():
    config = all_rules_config(ontology=ontology)
    # Self-binding, yes
    assoc = make_annotation(db="PomBase", db_id="SPAC25B8.17", goid="GO:0051260", withfrom="PomBase:SPAC25B8.17").associations[0]

    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.with_support_from = association.ConjunctiveSet.str_to_conjunctions("PomBase:BLAH123")
    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.with_support_from = association.ConjunctiveSet.str_to_conjunctions("PomBase:SPAC25B8.17|PomBase:BLAH123")
    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = Curie.from_str("GO:0000123")
    # Not in a self-binding mode
    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    # Test no ontology should just pass
    assoc.object.id = Curie.from_str("GO:0051260")
    test_result = qc.GoRule46().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule50():
    a = "PMID:21873635"
    assoc = make_annotation(db="HELLO", db_id="123", evidence="ISS", withfrom="HELLO:123").associations[0]

    test_result = qc.GoRule50().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.subject.id = Curie.from_str("BYE:567")
    test_result = qc.GoRule50().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    # Not ISS, so fine to have repeated columns
    assoc.subject.id = Curie.from_str("HELLO:123")
    assoc.evidence.type = Curie.from_str(iea_eco)
    test_result = qc.GoRule50().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS
    
def test_gorule51():
    assoc = make_annotation(goid="GO:0005515", extension="has_input(GO:0003674),occurs_in(CL:123456)").associations[0]

    test_result = qc.GoRule51().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc = make_annotation(goid="GO:0005488").associations[0]
    test_result = qc.GoRule51().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING      

def test_gorule55():
    a = ["blah"] * 15
    a[0] = "HELLO"
    a[1] = "123"
    a[3] = ""
    a[5] = "GO:0012345|PMID:1234567"
    a[6] = "ISS"
    a[7] = "HELLO:123"
    a[8] = "P"
    a[12] = "taxon:12345"
    a[13] = "20200303"
    assoc = make_annotation(db="HELLO", db_id="123", references="GO:0012345|PMID:1234567", evidence="ISS", withfrom="HELLO:123").associations[0]

    test_result = qc.GoRule55().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.has_supporting_reference = [association.Curie.from_str("GO:0001234"), association.Curie.from_str("GO:123456")]
    test_result = qc.GoRule55().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING


def test_gorule58():

    with open("tests/resources/extensions-constraints.yaml") as exs_cons:
        config = assocparser.AssocParserConfig(ontology=ontology, extensions_constraints=yaml.load(exs_cons, Loader=yaml.FullLoader), rule_set=assocparser.RuleSet.ALL)

    assoc = make_annotation(db="HELLO", db_id="123", goid="GO:0003674", evidence="IBA", references="PMID:21873635", aspect="P", assigned_by="GO_Central", extension="has_input(GO:0003674),occurs_in(CL:123456)").associations[0]

    test_result = qc.GoRule58().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    # Fails because `not_relation` is not an allowed relation
    new_ext = "coincident_with(GO:987),occurs_in(CL:1234567)|occurs_in(CL:12345)"
    assoc = make_annotation(db="HELLO", db_id="123", goid="GO:0003674", evidence="IBA", references="PMID:21873635", aspect="P", assigned_by="GO_Central", extension=new_ext).associations[0]
    test_result = qc.GoRule58().test(assoc, config)

    repaired_ext = "occurs_in(CL:12345)"
    expected_repair = make_annotation(db="HELLO", db_id="123", goid="GO:0003674", evidence="IBA", references="PMID:21873635", aspect="P", assigned_by="GO_Central", extension=repaired_ext).associations[0]
    expected_repair.source_line = assoc.source_line # Make sure original line is the same as test case
    assert test_result.result_type == qc.ResultType.WARNING
    assert test_result.result == expected_repair

    # Fails because `FOO` is not a real namespace for any `has_input` constraint
    new_ext = "has_input(FOO:1234566),occurs_in(CL:1234567)"
    assoc = make_annotation(db="HELLO", db_id="123", goid="GO:0003674", evidence="IBA", references="PMID:21873635", aspect="P", assigned_by="GO_Central", extension=new_ext).associations[0]
    test_result = qc.GoRule58().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    # Fails because this GO term is not in the constraint term children
    new_term = "GO:0005575"
    new_ext = "occurs_in(EMAPA:123),has_input(CL:1234567)"
    assoc = make_annotation(db="HELLO", db_id="123", goid=new_term, evidence="IBA", references="PMID:21873635", aspect="P", assigned_by="GO_Central", extension=new_ext).associations[0]
    test_result = qc.GoRule58().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    # Fails because of a cardinality check
    new_term = "GO:0003674"
    new_ext = "occurs_in(EMAPA:123),occurs_in(EMAPA:1987654)"
    assoc = make_annotation(db="HELLO", db_id="123", goid=new_term, evidence="IBA", references="PMID:21873635", aspect="P", assigned_by="GO_Central", extension=new_ext).associations[0]
    test_result = qc.GoRule58().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

def test_gorule61():
    config = all_rules_config(ontology=ontology)
    assoc = make_annotation(goid="GO:0003674", qualifier="enables", evidence=ikr_eco, from_gaf=False, version="1.2")
    assert assoc.report.reporter.messages.get("gorule-0000001", []) == []
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.PASS

    # Using `contributes_to`, but should be repaired to RO:0002327 enables
    assoc = make_annotation(goid="GO:0003674", qualifier="contributes_to", evidence=ikr_eco, from_gaf=False, version="1.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result.relation == association.Curie("RO", "0002327")
    assert test_result.result_type == qc.ResultType.WARNING

    # BP term, qualifier inside allowed BP set
    assoc = make_annotation(goid="GO:0016192", qualifier="acts_upstream_of_or_within", evidence=ikr_eco, from_gaf=False, version="1.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.PASS

    # BP term, unallowed relation, Repair
    assoc = make_annotation(goid="GO:0016192", qualifier="enables", evidence=ikr_eco, from_gaf=False, version="1.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.WARNING
    assert test_result.result.relation == association.Curie("RO", "0002264")

    # CC complex term, qualifier is allowed
    assoc = make_annotation(goid="GO:0032991", qualifier="part_of", evidence=ikr_eco, from_gaf=False, version="1.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.PASS

    # CC complex term, unallowed relation, repairable, causes warning
    assoc = make_annotation(goid="GO:0032991", qualifier="enables", evidence=ikr_eco, from_gaf=False, version="1.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.WARNING

    # CC root repairs to is_active_in
    assoc = make_annotation(goid="GO:0005575", qualifier="located_in", evidence="ND", from_gaf=True, version="2.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.WARNING
    # Active in, rather than located_in
    assert test_result.result.relation == association.Curie(namespace="RO", identity="0002432")

    # protein complex + repairable relation repairs to part_of
    assoc = make_annotation(goid="GO:0032991", qualifier="is_active_in", evidence=ikr_eco, from_gaf=False, version="1.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.WARNING
    assert test_result.result.relation == association.Curie(namespace="BFO", identity="0000050")

    # obsoleted term - these won't have namespace in ontology so ensure they aren't failed by this rule 61
    # instead should be handled by rule 20
    assoc = make_annotation(goid="GO:1902361", qualifier="involved_in", evidence="ISS", from_gaf=True,
                            version="2.2")
    test_result = qc.GoRule61().test(assoc.associations[0], config)
    assert test_result.result_type == qc.ResultType.PASS
        
def test_go_rule_63():
    # ISS with anything in withfrom
    assoc = make_annotation(evidence="ISS", withfrom="BLAH:12345").associations[0]
    test_result = qc.GoRule63().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS

    # ISA with anything in withfrom
    assoc = make_annotation(evidence="ISA", withfrom="BLAH:12345").associations[0]
    test_result = qc.GoRule63().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS
    
    # ISO with anything in withfrom
    assoc = make_annotation(evidence="ISO", withfrom="BLAH:12345").associations[0]
    test_result = qc.GoRule63().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.PASS    

    # ISS with nothing in withfrom
    assoc = make_annotation(evidence="ISS", withfrom="").associations[0]
    test_result = qc.GoRule63().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING

    # ISA with  with nothing in withfrom
    assoc = make_annotation(evidence="ISA", withfrom="").associations[0]
    test_result = qc.GoRule63().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING
    
    # ISO with  with nothing in withfrom
    assoc = make_annotation(evidence="ISO", withfrom="").associations[0]
    test_result = qc.GoRule63().test(assoc, all_rules_config())
    assert test_result.result_type == qc.ResultType.WARNING
    
def test_go_rule_64():
    config = assocparser.AssocParserConfig(
        ref_species_metadata={
            "NCBITaxon:7227", "NCBITaxon:123"
        },
        rule_set=assocparser.RuleSet.ALL
    )
            
    assoc = make_annotation(evidence="IEA", references="GO_REF:0000118").associations[0]
    assoc.subject.taxon = Curie.from_str("NCBITaxon:678")
    test_result = qc.GoRule64().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc = make_annotation(evidence="IBA", references="GO_REF:0000118").associations[0]
    assoc.subject.taxon = Curie.from_str("NCBITaxon:123")
    test_result = qc.GoRule64().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS
    
    assoc = make_annotation(evidence="IEA", references="GO_REF:0000123").associations[0]
    assoc.subject.taxon = Curie.from_str("NCBITaxon:123")
    test_result = qc.GoRule64().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS         

    assoc = make_annotation(evidence="IEA", references="GO_REF:0000118").associations[0]
    assoc.subject.taxon = Curie.from_str("NCBITaxon:7227")
    test_result = qc.GoRule64().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR
    
def test_go_rule65():

    assoc = make_annotation(goid="GO:0099531").associations[0]

    test_result = qc.GoRule65().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING
    
    assoc = make_annotation(goid="GO:0016192").associations[0]
    test_result = qc.GoRule65().test(assoc, all_rules_config(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS
    
     

def test_all_rules():
    # pass
    config = all_rules_config(ontology=ontology)
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0006397"
    a[5] = "PMID:21873635"
    a[6] = "ISS"
    a[7] = "PomBase:SPAC25B8.17"
    a[8] = "P"
    a[12] = "taxon:123"
    a[13] = "20180330"
    assoc = gafparser.to_association(a).associations[0]

    test_results = qc.test_go_rules(assoc, config).all_results
    assert len(test_results.keys()) == 28
    assert test_results[qc.GoRules.GoRule26.value].result_type == qc.ResultType.PASS
    assert test_results[qc.GoRules.GoRule29.value].result_type == qc.ResultType.PASS


if __name__ == "__main__":
    pytest.main(args=["tests/test_qc.py"])
