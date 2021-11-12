"""
Dataclasses used in scigraph_util

These were originally autogenerated from the biolink-api
marshmallow definitions

See original classes here:
https://raw.githubusercontent.com/biolink/biolink-api/1e81503/biomodel/core.py
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ontobio.util.curie_map import get_curie_map

from prefixcommons.curie_util import expand_uri


@dataclass
class NamedObject:
    """
    NamedObject

    Arguments
    ---------
     id :

         ID or CURIE e.g. MGI:1201606

     label :

         RDFS Label

     iri :

         IRI

     category :

         Type of object

     description :

         Description (or definition) of an object

     types :

         Type of object (direct)

     synonyms :

         list of synonyms or alternate labels

     replaced_by :

         Direct 1:1 replacement (if named object is obsoleted)

     consider :

         Potential replacement object (if named object is obsoleted)
    """
    id: str = None
    lbl: Optional[str] = None
    iri: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    types: Optional[List[str]] = field(default_factory=list)
    synonyms: Optional[List[str]] = field(default_factory=list)
    deprecated: Optional[bool] = None
    replaced_by: Optional[List[str]] = field(default_factory=list)
    consider: Optional[List[str]] = field(default_factory=list)
    meta: Optional[Dict] = field(default_factory=dict)

    def __post_init__(self):
        """
        Logic moved from scigraph_util.map_tuple
        """
        if self.lbl:
            self.label = self.lbl

        if 'category' in self.meta:
            self.category = self.category or self.meta['category']

        self.iri = self.iri or expand_uri(self.id, [get_curie_map()])

        if 'synonym' in self.meta:
            self.synonyms = self.synonyms or [
                SynonymPropertyValue(pred='synonym', val=s) for s in self.meta['synonym']
            ]

        if 'definition' in self.meta and self.meta['definition']:
            self.description = self.description or self.meta['definition'][0]

@dataclass
class Taxon:
    id: Optional[str] = None
    lbl: Optional[str] = None

    def __post_init__(self):
        if self.lbl:
            self.label = self.lbl



@dataclass
class BioObject(NamedObject):
    """
    BioObject

    Superclass: NamedObject
    """

    taxon: Optional[Taxon] = None
    association_counts: Optional[int] = None
    xrefs: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()

        if 'http://www.geneontology.org/formats/oboInOwl#hasDbXref' in self.meta:
            self.xrefs = self.xrefs or self.meta['http://www.geneontology.org/formats/oboInOwl#hasDbXref']


@dataclass
class Disease(BioObject):
    inheritance: Optional[List[NamedObject]] = field(default_factory=list)
    clinical_modifiers: Optional[List[NamedObject]] = field(default_factory=list)


@dataclass
class AbstractPropertyValue:
    """
    AbstractPropertyValue

    Arguments
    ---------
     val :

         value part

     pred :

         predicate (attribute) part

     xrefs :

         Xrefs provenance for property-value
    """

    val: Optional[str] = None
    pred: Optional[str] = None
    xrefs: Optional[List[str]] = field(default_factory=list)


@dataclass
class SynonymPropertyValue(AbstractPropertyValue):
    """
    SynonymPropertyValue

    Superclass: AbstractPropertyValue
    """
    id: Optional[str] = None