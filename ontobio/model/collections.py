import typing
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Callable

from ontobio.model import association
from ontobio.model.association import GoAssociation, Subject, Curie, Union, Optional
from ontobio.io import parser_version_regex
from ontobio.io import assocparser, gafparser, gpadparser, entityparser

logger = logging.getLogger(__name__)

@dataclass
class BioEntities:
    entities: Dict[Curie, Subject]

    def merge(self, other):
        """
        Merge another BioEntity set into this one. The `other` set will
        override any collisions in this BioEntities
        """
        self.entities.update(other.entities)
        return self

    def get(self, entity_id: Curie) -> Optional[Subject]:
        """
        Using an entity ID Curie, attempt to obtain the BioEntity `Subject` with
        this ID. If not present, this returns `None`.
        """
        return self.entities.get(entity_id, None)

    @classmethod
    def load_from_file(BioEntities, path: str):
        entities = dict() # type: Dict[Curie, Subject]
        print("loading from {}".format(path))
        try:
            gpi_parser = entityparser.GpiParser()
            with open(path) as gpi:
                for line in gpi:

                    ents = gpi_parser.line_as_entity_subject(line)
                    if ents is None:
                        continue

                    for entity in ents:
                        entity_id = entity.id
                        entities[entity_id] = entity

        except Exception as e:
            logger.error("Failed to read GPI file: {}".format(str(e)))

        return BioEntities(entities)

@dataclass
class GoAssociations:
    associations: List[GoAssociation]

@dataclass
class AssociationCollection:
    headers: List[str]
    associations: GoAssociations
    entities: BioEntities
    report: assocparser.Report

    @classmethod
    def initial(cls):  # type AssociationCollection
        return AssociationCollection([], GoAssociations([]), BioEntities(dict()), assocparser.Report())


def create_parser_from_header(line: str, config: assocparser.AssocParserConfig, group="unknown", dataset="unknown", bio_entities=None) -> Optional[assocparser.AssocParser]:
    parser = None
    parsed_version = parser_version_regex.findall(line)
    if len(parsed_version) == 1:
        filetype, version, _ = parsed_version[0]
        if filetype in ["gpad", "gpa"]:
            parser = gpadparser.GpadParser(config=config, bio_entities=bio_entities, group=group, dataset=dataset)
            if version in ["1.2", "2.0"]:
                parser.version = version
        elif filetype == "gaf":
            parser = gafparser.GafParser(config=config, bio_entities=bio_entities, group=group, dataset=dataset)
            if version in ["2.1", "2.2"]:
                parser.version = version

    return parser


def construct_collection(annotation_path: Optional[str], gpi_paths: List[str], config: assocparser.AssocParserConfig) -> AssociationCollection:
    entities = BioEntities(dict())
    for gpi in gpi_paths:
        entities.merge(BioEntities.load_from_file(gpi))

    annotations = []
    headers = []
    report = assocparser.Report()
    if annotation_path:
        parser = GeneralAssocParser(config, "unknown", bio_entities=entities)
        try:
            annotations = parser.parse(annotation_path)
        except NoVersionInFile as e:
            parser.report = e.report
            annotations = []

        headers = parser.headers
        report = parser.report

    return AssociationCollection(headers, GoAssociations(annotations), entities, report)


@dataclass
class NoVersionInFile(Exception):
    message: str
    report: assocparser.Report

    def __str__(self):
        return "NoVersionInFile: {}".format(self.message)

@dataclass
class GeneralAssocParser(assocparser.AssocParser):
    config: assocparser.AssocParserConfig
    group: str
    headers: List[str] = field(default_factory=list)
    report: assocparser.Report = field(default_factory=lambda: assocparser.Report())
    bio_entities: BioEntities = field(default_factory=lambda: BioEntities(dict()))
    annotation_parser: Optional[assocparser.AssocParser] = None

    def parse_line(self, line):
        parsed = super().validate_line(line)
        if parsed:
            return parsed

        if self.is_header(line):
            if self.annotation_parser is None:
                # We're still looking for a version identifier
                parser = create_parser_from_header(line, self.config, bio_entities=self.bio_entities)
                if parser is not None:
                    self.annotation_parser = parser
                    self.report = parser.report

            self.headers.append(line)
            return assocparser.ParseResult(line, [], skipped=False)

        # At this point, we are not going through headers, and so we should have selected a parser
        if self.annotation_parser is None:
            logger.error("File is bad! We need to bail here!")
            self.report.error("", "Invalid Annotation File", "", "File header is missing file and version", rule=1)
            raise NoVersionInFile("File has no version info", self.report)

        # Just hand off parse responsibility to underlying `annotation_parser`
        return self.annotation_parser.parse_line(line)
