import click
import os

from ontobio.rdfgen import assoc_rdfgen
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio import ontol_factory

@click.group()
def cli():
    pass

@cli.command()
@click.option("--association", "-a", default="gaf", type=click.Choice(["gaf"]))
@click.option("--ontology", "-r", type=click.Path(exists=True, readable=True, dir_okay=False))
@click.option("--output", "-o", type=click.File('wb'))
@click.argument("association_file", type=click.Path(exists=True))
def convert(association, ontology, output, association_file):
    click.echo("converting {}".format(association))

    rdfWriter = assoc_rdfgen.TurtleRdfWriter(label=os.path.basename(output.name))
    rdfTransformer = assoc_rdfgen.CamRdfTransform(writer=rdfWriter)
    parser_config = assocparser.AssocParserConfig(ontology=make_ontology(ontology))
    parser = _association_parser(association, parser_config)

    with open(association_file) as af:
        lines = sum(1 for line in af)

    with open(association_file) as af:
        associations = parser.association_generator(file=af)
        with click.progressbar(iterable=associations, length=lines) as assocs:
            for assoc in assocs:
                rdfTransformer.provenance()
                rdfTransformer.translate(assoc)

        click.echo("Writing ttl to disk")
        rdfWriter.serialize(destination=output)


def _association_parser(association_type, config):
    if association_type == "gaf":
        return gafparser.GafParser(config=config)

def make_ontology(input_ontology):
    click.echo("Loading ontology...")
    ontology_factory = ontol_factory.OntologyFactory()
    return ontology_factory.create(input_ontology)


if __name__ == "__main__":
    cli()
