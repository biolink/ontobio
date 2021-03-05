#!/usr/bin/env python3

import click
import os
import csv
import pandas as pd

from ontobio import OntologyFactory
from ontobio.tsv_expander import expand_tsv

@click.group()
def cli():
    pass

@cli.command()
@click.option("--ontology", "-r")
@click.option("--output", "-o", type=click.File('w'))
@click.argument("tsvfile", type=click.Path(exists=True))
@click.argument("cols", nargs=-1)
def expand(tsvfile, cols, ontology, output):

    factory = OntologyFactory()
    ontobj = factory.create(ontology)
    expand_tsv(tsvfile, ontology=ontobj, outfile=output, cols=cols)


if __name__ == "__main__":
    cli()
