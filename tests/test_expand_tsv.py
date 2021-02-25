from ontobio import OntologyFactory
from ontobio.tsv_expander import expand_tsv
import csv


INPUT = "tests/resources/data_table.tsv"
OUTPUT = "tests/resources/data_table-expanded.tsv"

def test_expand():
    factory = OntologyFactory()
    ontobj = factory.create("tests/resources/goslim_pombe.json")
    expand_tsv(INPUT, ontology=ontobj, outfile=open(OUTPUT,"w"), cols=["term"])
    reader = csv.DictReader(open(OUTPUT, "r"), delimiter='\t')
    n=0
    for row in reader:
        if row['term'] == 'GO:0002181':
            assert row['term_label'] == 'cytoplasmic translation'
            n += 1
        if row['term'] == 'FAKE:123':
            assert row['term_label'] == ''
            n += 1
    assert n == 2
