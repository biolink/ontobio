from ontobio.io.gpadparser import GpadParser, to_association
from ontobio.io import assocparser
from ontobio.model import association
from ontobio.model.association import ConjunctiveSet, ExtensionUnit, Curie
from ontobio.ontol_factory import OntologyFactory
from ontobio.model import collections
from ontobio.model.association import Curie, Subject

import yaml
import re

POMBASE = "tests/resources/truncated-pombase.gpad"
ALT_ID_ONT = "tests/resources/obsolete.json"

def test_obsolete_term_repair_withfrom():

    vals = ["ZFIN",
            "ZFIN:ZDB-GENE-980526-362",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:15494018",
            "ECO:0000305",
            "GO:0005913|GO:1,GO:4|ZFIN:ZDB-MRPHLNO-010101-1,MGI:1232453",
            "",
            "20041026",
            "ZFIN",
            "",
            "contributor=GOC:zfin_curators|model-state=production|noctua-model-id=gomodel:ZFIN_ZDB-GENE-980526-362"
            ]
    ont = OntologyFactory().create(ALT_ID_ONT)
    config = assocparser.AssocParserConfig(ontology=ont, rule_set=assocparser.RuleSet.ALL)
    parser = GpadParser(config=config)
    result = parser.parse_line("\t".join(vals))
    assoc = result.associations[0]
    # GO:0005913 should be repaired to its replacement term, GO:00005912
    assert [ConjunctiveSet(elements=[Curie(namespace='GO', identity='0005912')]),
            # repaired test GO elements
            ConjunctiveSet(elements=[Curie(namespace='GO', identity='2'), Curie(namespace='GO', identity='3')]),
            # non GO elements stay the same, could be obsolete or not
            ConjunctiveSet(elements=[Curie(namespace='ZFIN', identity='ZDB-MRPHLNO-010101-1'),
                                     Curie(namespace='MGI', identity='1232453')])] == assoc.evidence.with_support_from


    obsolete_go_with_from_no_replacement = ["ZFIN",
            "ZFIN:ZDB-GENE-980526-362",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:15494018",
            "ECO:0000305",
            "GO:0016458|GO:1,GO:4|ZFIN:ZDB-MRPHLNO-010101-1,MGI:1232453",
            "",
            "20041026",
            "ZFIN",
            "",
            "contributor=GOC:zfin_curators|model-state=production|noctua-model-id=gomodel:ZFIN_ZDB-GENE-980526-362"
            ]
    ont = OntologyFactory().create(ALT_ID_ONT)
    config = assocparser.AssocParserConfig(ontology=ont, rule_set=assocparser.RuleSet.ALL)
    parser = GpadParser(config=config)
    result = parser.parse_line("\t".join(obsolete_go_with_from_no_replacement))
    assert result.associations == []

def test_obsolete_term_repair_extensions():

    vals = ["ZFIN",
            "ZFIN:ZDB-GENE-980526-362",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:15494018",
            "ECO:0000305",
            "ZFIN:ZDB-MRPHLNO-010101-1,MGI:1232453",
            "",
            "20041026",
            "ZFIN",
            "part_of(GO:0005913)|occurs_in(GO:1),has_input(GO:4)|enables(ZFIN:ZDB-MRPHLNO-010101-1),enables(MGI:1232453)",
            "contributor=GOC:zfin_curators|model-state=production|noctua-model-id=gomodel:ZFIN_ZDB-GENE-980526-362"
            ]
    ont = OntologyFactory().create(ALT_ID_ONT)
    config = assocparser.AssocParserConfig(ontology=ont, rule_set=assocparser.RuleSet.ALL)
    parser = GpadParser(config=config)
    result = parser.parse_line("\t".join(vals))
    assoc = result.associations[0]
    # GO:0005913 should be repaired to its replacement term, GO:00005912
    object_extensions = [association.ConjunctiveSet([association.ExtensionUnit(association.Curie("BFO", "0000050"), association.Curie("GO", "0005912"))]),
            # repaired test GO elements
            association.ConjunctiveSet([association.ExtensionUnit(association.Curie("BFO", "0000066"), association.Curie(namespace='GO', identity='2')),association.ExtensionUnit(association.Curie("RO", "0002233"), association.Curie(namespace='GO', identity='3'))]),
            # non GO elements stay the same, could be obsolete or not
            association.ConjunctiveSet([association.ExtensionUnit(association.Curie("RO", "0002327"), association.Curie(namespace='ZFIN', identity='ZDB-MRPHLNO-010101-1')),association.ExtensionUnit(association.Curie("RO", "0002327"), association. Curie(namespace='MGI', identity='1232453'))])
            ]
    assert object_extensions == assoc.object_extensions


def test_skim():
    p = GpadParser()
    results = p.skim(open(POMBASE,"r"))
    print(str(results))


def test_parse():
    p = GpadParser(config=assocparser.AssocParserConfig(group_metadata=yaml.load(open("tests/resources/mgi.dataset.yaml"), Loader=yaml.FullLoader)))
    test_gpad_file = "tests/resources/mgi.test.gpad"
    results = p.parse(open(test_gpad_file, "r"))
    print(p.report.to_markdown())


def test_gpad_association_generator_header_report():
    p = GpadParser(config=assocparser.AssocParserConfig(group_metadata=yaml.load(open("tests/resources/mgi.dataset.yaml"),
                                                                                 Loader=yaml.FullLoader)))
    test_gpad_file = "tests/resources/mgi.test.gpad"
    assert len(p.report.header) == 0
    for a in p.association_generator(open(test_gpad_file, "r")):
        continue
    assert len(p.report.header) > 0


def test_parse_1_2():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI",
        "MGI:1918911",
        "enables",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "20100209",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="1.2")
    assert result.skipped == 0
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 0
    assert len(result.associations) == 1


def test_parse_interacting_taxon():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI",
        "MGI:1918911",
        "enables",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "taxon:5678",
        "20100209",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="1.2")
    assert result.associations[0].interacting_taxon == Curie(namespace="NCBITaxon", identity="5678")
    
def test_parse_go_id_1_2():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI",
        "MGI:1918911",
        "enables",
        "UBERON:1234",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "20100209",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="1.2")
    assert result.skipped == 1
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 1
    assert len(result.associations) == 0    


def test_duplicate_key_annot_properties():
    properties_str = "creation-date=2008-02-07|modification-date=2010-12-01|comment=v-KIND domain binding of Kndc1;MGI:1923734|contributor-id=http://orcid.org/0000-0003-2689-5511|contributor-id=http://orcid.org/0000-0003-3394-9805"
    prop_list = association.parse_annotation_properties(properties_str)
    contributor_ids = [value for key, value in prop_list if key == "contributor-id"]
    assert set(contributor_ids) == {"http://orcid.org/0000-0003-2689-5511", "http://orcid.org/0000-0003-3394-9805"}


def test_parse_2_0():
    version = "2.0"
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI:MGI:1918911",
        "",
        "RO:0002327",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "2020-09-17",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version=version)
    assert result.skipped == 0
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 0
    assert len(result.associations) == 1

    # Annotation_Extensions
    vals[10] = "BFO:0000066(CL:0000010),GOREL:0001004(CL:0000010)"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].object_extensions == [ConjunctiveSet([
            ExtensionUnit(Curie("BFO", "0000066"), Curie("CL", "0000010")),
            ExtensionUnit(Curie("GOREL", "0001004"), Curie("CL", "0000010"))
        ])]

    # With_or_From
    vals[6] = "PR:Q505B8|PR:Q8CHK4"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].evidence.with_support_from == [
        ConjunctiveSet([Curie("PR", "Q505B8")]),
        ConjunctiveSet([Curie("PR", "Q8CHK4")])
    ]

    # Interacting taxon - this example should fail
    vals[7] = "Staphylococcus aureus ; NCBITaxon:1280"
    result = to_association(list(vals), report=report, version=version)
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) > 0
    assert len(result.associations) == 0
    # Now test valid interacting taxon value
    vals[7] = "NCBITaxon:1280"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].interacting_taxon == Curie("NCBITaxon", "1280")

    # Confirm non-"MGI:MGI:" IDs will parse
    vals[0] = "WB:WBGene00001189"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].subject.id == Curie("WB", "WBGene00001189")

    # Test annotation property retrieval
    contributors = result.associations[0].annotation_property_values(property_key="contributor-id")
    assert set(contributors) == {"http://orcid.org/0000-0003-2689-5511"}
    
    
def test_parse_go_id_2_0():
    version = "2.0"
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI:MGI:1918911",
        "",
        "RO:0002327",
        "UBERON:5678",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "2020-09-17",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version=version)
    assert result.skipped == 1
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 1
    assert len(result.associations) == 0    


def test_aspect_fill_for_obsolete_terms():
    # Test null aspect on an obsolete term
    # GO:4 is obsolete and has no aspect (hasOBONamespace) in obsolete.json ontology
    # GO:3 is it's replacement term
    # Note that GPAD lines contain no aspect data
    vals = [
        "MGI",
        "MGI:105128",
        "involved_in",
        "GO:4",
        "PMID:25901318",
        "ECO:0000314",
        "",
        "",
        "20190517",
        "MGI",
        "",
        "contributor=http://orcid.org/0000-0002-9796-7693|model-state=production|noctua-model-id=gomodel:5c4605cc00004132"
    ]
    ont = OntologyFactory().create(ALT_ID_ONT)
    config = assocparser.AssocParserConfig(ontology=ont, rule_set=assocparser.RuleSet.ALL)
    parser = GpadParser(config=config)
    result = parser.parse_line("\t".join(vals))
    assoc = result.associations[0]

    assert assoc.object.id == Curie("GO", "3")  # GO:4 should be repaired to its replacement term, GO:3
    assert assoc.aspect == 'P'  # Aspect should not be empty


def test_unmapped_eco_to_gaf_codes():
    # By default, ECO codes in GPAD need to be convertible to an ECO GAF code (e.g. IDA, ISO)
    vals = [
        "MGI",
        "MGI:88276",
        "is_active_in",
        "GO:0098831",
        "PMID:8909549",
        "ECO:0000164",
        "",
        "",
        "20180711",
        "SynGO",
        "part_of(UBERON:0000956)",
        ""
    ]
    parser = GpadParser(config=assocparser.AssocParserConfig())
    result = parser.parse_line("\t".join(vals))
    assert len(result.associations) == 0
    messages = parser.report.messages
    assert messages[0]["type"] == parser.report.UNKNOWN_EVIDENCE_CLASS

    parser.config.allow_unmapped_eco = True
    result = parser.parse_line("\t".join(vals))
    assert len(result.associations) == 1

    parser.config.allow_unmapped_eco = False
    vals[5] = "ECO:0000314"  # maps to IDA
    result = parser.parse_line("\t".join(vals))
    assert len(result.associations) == 1

    vals[5] = "ECO:0006003"  # indirectly maps to IDA via gaf-eco-mapping-derived.txt
    result = parser.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    
def test_id_syntax():
    database_id_syntax_lookups = {}
    go_types = {}
    pattern = '\\d{7}'
    go_types['molecular_function'] = re.compile(pattern)
    go_types['biological_process'] = re.compile(pattern)
    go_types['cellular_component'] = re.compile(pattern)      
    database_id_syntax_lookups['GO'] = go_types
    
    pmid_types = {}
    pmid_types['entity'] = re.compile('[0-9]+')
    database_id_syntax_lookups['PMID'] = pmid_types
    
    pombase_types = {}
    pombase_types['entity'] = re.compile('S\\w+(\\.)?\\w+(\\.)?')
    database_id_syntax_lookups['PomBase'] = pombase_types
    
    mgi_types = {}
    mgi_types['entity'] = re.compile('MGI:[0-9]{5,}')
    database_id_syntax_lookups['MGI'] = mgi_types    
    
    eco_types = {}
    eco_types['entity'] = re.compile(pattern)
    database_id_syntax_lookups['ECO'] = eco_types
    
    wb_ref_types = {}
    database_id_syntax_lookups['WB_REF'] = wb_ref_types     
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:15494018",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]

    config = assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ALT_ID_ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups)
    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False  
    messages = p.report.to_report_json()["messages"]
    assert "gorule-0000027" not in messages       
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "WB_REF:WBPaper00006408|PMID:15494018",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]

    config = assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ALT_ID_ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups)
    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False  
    messages = p.report.to_report_json()["messages"]
    assert "gorule-0000027" not in messages
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "MGI:MGI:1298204",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]

    config = assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ALT_ID_ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups)
    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False  
    messages = p.report.to_report_json()["messages"]
    assert "gorule-0000027" not in messages    
         
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:PMID:15494018",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]

    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "PMID:PMID:15494018"
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:9.",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]

    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "PMID:9." 
    
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "PMID:a1549418",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]

    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "PMID:a1549418" 
         

    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "BLA:15494018",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]
    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "BLA:15494018"   
    
    vals = ["PomBase",
            "SPAC25A8.01c",
            "acts_upstream_of_or_within",
            "GO:0007155",
            "MGI:15494018",
            "ECO:0000305",
            "GO:0005913",
            "",
            "20041026",
            "ZFIN",
            "",
            "PomBase"
            ]
    p = GpadParser(config=config)
    result = p.parse_line("\t".join(vals))
    assert len(result.associations) == 1
    assert result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "MGI:15494018"       
    
    
def test_gpi_check():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "ZFIN",
        "ZDB-GENE-070117-1552",
        "acts_upstream_of_or_within",
        "GO:0045601",
        "PMID:17531218",
        "ECO:0000307",
        "",
        "",
        "20080326",
        "ZFIN",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    
    bioentities = collections.BioEntities({
        Curie("ZFIN", "ZDB-GENE-070117-1552"): Subject(Curie.from_str("ZFIN:ZDB-GENE-070117-1552"), "ste4", ["adaptor protein Ste4"], [], ["protein"], Curie.from_str("taxon:0"))
        })
    
    
    result = to_association(list(vals), report=report, version="1.2", bio_entities=bioentities)
    assert result.skipped == True
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 1
    assert len(result.associations) == 0 
    
    bioentities = collections.BioEntities({
        Curie("ZFIN", "ZDB-GENE-070117-1552"): Subject(Curie.from_str("ZFIN:ZDB-GENE-070117-1552"), "ste4", ["adaptor protein Ste4"], [], ["protein"], Curie.from_str("taxon:987x65"))
        })
    
    result = to_association(list(vals), report=report, version="1.2", bio_entities=bioentities)
    assert result.skipped == True
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 2
    assert len(result.associations) == 0        
    
    bioentities = collections.BioEntities({
        Curie("ZFIN", "ZDB-GENE-070117-1552"): Subject(Curie.from_str("ZFIN:ZDB-GENE-070117-1552"), "ste4", ["adaptor protein Ste4"], [], ["protein"], Curie.from_str("taxon:0"))
        })    
    
    vals = [
        "ZFIN:ZDB-GENE-070117-1552",
        "ZFIN:ZDB-GENE-070117-1552",
        "RO:12345",
        "GO:0045601",
        "PMID:17531218",
        "ECO:0000307",
        "",
        "",
        "2008-03-26",
        "ZFIN",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="2.0", bio_entities=bioentities)
    assert result.skipped == True
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 3
    assert len(result.associations) == 0     
    
    
    bioentities = collections.BioEntities({"bla": 'blabla'})

    result = to_association(list(vals), report=report, version="2.0", bio_entities=bioentities)
    assert result.skipped == True
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 4
    assert len(result.associations) == 0    
    
    bioentities = collections.BioEntities({
        Curie("ZFIN", "ZDB-GENE-070117-1552"): Subject(Curie.from_str("ZFIN:ZDB-GENE-070117-1552"), "ste4", ["adaptor protein Ste4"], [], ["protein"], Curie.from_str("NCBITaxon:12345"))
        })

    result = to_association(list(vals), report=report, version="2.0", bio_entities=bioentities)
    assert result.skipped == 0
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 4
    assert len(result.associations) == 1 
        
    bioentities = collections.BioEntities({
        Curie("ZFIN", "ZDB-GENE-070117-1552"): Subject(Curie.from_str("ZFIN:ZDB-GENE-070117-1552"), "ste4", ["adaptor protein Ste4"], [], ["protein"], Curie.from_str("NCBITaxon:12abc5"))
        })
    result = to_association(list(vals), report=report, version="2.0", bio_entities=bioentities)
    assert result.skipped == True
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 5
    assert len(result.associations) == 0       