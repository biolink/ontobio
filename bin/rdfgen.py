import click

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
@click.argument("association_file", type=click.File('r'))
def convert(association, ontology, output, association_file):
    click.echo("converting {}".format(association))

    rdfWriter = assoc_rdfgen.TurtleRdfWriter()
    rdfTransformer = assoc_rdfgen.CamRdfTransform(writer=rdfWriter)
    parser_config = assocparser.AssocParserConfig(ontology=make_ontology(ontology))
    parser = _association_parser(association, parser_config)

    associations = parser.association_generator(file=association_file)
    for assoc in associations:
        rdfTransformer.provenance()
        rdfTransformer.translate(assoc)

    rdfWriter.serialize(destination=output)


def _association_parser(association_type, config):
    if association_type == "gaf":
        return gafparser.GafParser(config=config)

def make_ontology(input_ontology):
    ontology_factory = ontol_factory.OntologyFactory()
    return ontology_factory.create(input_ontology)


if __name__ == "__main__":
    cli()
