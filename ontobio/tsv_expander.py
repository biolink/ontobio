import csv
import logging
from typing import List
from ontobio.ontol import Ontology

def expand_tsv(input: str, ontology: Ontology = None, outfile=None, sep='\t', cols: List[str]=None) -> None:
    """
    Adds additional columns to a TSV by performing additional ontology lookups

    For example, given a TSV with a column `term`, this can add a column `term_label`
    in future it may also add closures

    :param input: filename of a TSV (must have column headers)
    :param ontology: used for lookup
    :param outfile: pathname for output file
    :param sep: delimiter
    :param cols: names of columns
    :return:
    """
    with open(input, newline='') as io:
        reader = csv.DictReader(io, delimiter='\t')
        items = []
        if True:
            outwriter = csv.writer(outfile, delimiter=sep)
            first = True
            for row in reader:
                if first:
                    first = False
                    hdr = []
                    for k in row.keys():
                        hdr.append(k)
                        if k in cols:
                            hdr.append(f'{k}_label')
                    outwriter.writerow(hdr)
                vals = []
                for k,v in row.items():
                    vals.append(v)
                    if k in cols:
                        id = row[k]
                        label = ontology.label(id)
                        vals.append(label)
                        if label is None:
                            logging.warning(f"No id: {id}")
                        #item[f'{k}_label'] = label
                outwriter.writerow(vals)

