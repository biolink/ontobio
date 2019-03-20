from ontobio.io import assocparser
from ontobio.io import entityparser
from ontobio.io import entitywriter
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION

import logging

class GpadParser(assocparser.AssocParser):
    """
    Parser for GO GPAD Format

    https://github.com/geneontology/go-annotation/blob/master/specs/gpad-gpi-1_2.md
    """


    def __init__(self, config=assocparser.AssocParserConfig(), group="unknown", dataset="unknown"):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        self.report = assocparser.Report(config=self.config, group="unknown", dataset="unknown")
        self.gpi = None
        if self.config.gpi_authority_path is not None:
            self.gpi = dict()
            parser = entityparser.GpiParser()
            with open(self.config.gpi_authority_path) as gpi_f:
                entities = parser.parse(file=gpi_f)
                for entity in entities:
                    self.gpi[entity["id"]] = {
                        "symbol": entity["label"],
                        "name": entity["full_name"],
                        "synonyms": entitywriter.stringify(entity["synonyms"]),
                        "type": entity["type"]
                    }
                print("Loaded {} entities from {}".format(len(self.gpi.keys()), self.config.gpi_authority_path))


    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) != 12:
                logging.error("Unexpected number of columns: {}. GPAD should have 12.".format(vals))
            rel = vals[2]

            negated, relation, _ = self._parse_qualifier(vals[2], None)

            # never include NOTs in a skim
            if negated:
                continue
            if self._is_exclude_relation(relation):
                continue


            id = self._pair_to_id(vals[0], vals[1])
            if not self._validate_id(id, line, context=ENTITY):
                continue
            t = vals[3]
            tuples.append( (id,None,t) )
        return tuples

    def parse_line(self, line):
        """Parses a single line of a GPAD.

        Return a tuple `(processed_line, associations)`. Typically
        there will be a single association, but in some cases there
        may be none (invalid line) or multiple (disjunctive clause in
        annotation extensions)

        Note: most applications will only need to call this directly if they require fine-grained control of parsing. For most purposes,
        :method:`parse_file` can be used over the whole file

        Arguments
        ---------
        line : str
            A single tab-seperated line from a GPAD file

        """
        parsed = super().validate_line(line)
        if parsed:
            return parsed

        if self.is_header(line):
            return assocparser.ParseResult(line, [{ "header": True, "line": line.strip() }], False)

        vals = [el.strip() for el in line.split("\t")]
        if len(vals) < 10 or len(vals) > 12:
            self.report.error(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
                msg="There were {columns} columns found in this line, and there should be between 10 and 12".format(columns=len(vals)))
            return assocparser.ParseResult(line, [], True)

        if len(vals) < 12:
            vals += [""] * (12 - len(vals))

        [db,
         db_object_id,
         qualifier,
         goid,
         reference,
         evidence,
         withfrom,
         interacting_taxon_id,
         date,
         assigned_by,
         annotation_xp,
         annotation_properties] = vals

        split_line = assocparser.SplitLine(line=line, values=vals, taxon="")

        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, split_line, context=ENTITY):
            return assocparser.ParseResult(line, [], True)

        if not self._validate_id(goid, split_line, context=ANNOTATION):
            return assocparser.ParseResult(line, [], True)

        valid_goid = self._validate_ontology_class_id(goid, split_line)
        if valid_goid == None:
            return assocparser.ParseResult(line, [], True)
        goid = valid_goid

        date = self._normalize_gaf_date(date, split_line)

        if reference == "":
            self.report.error(line, Report.INVALID_ID, "EMPTY", "reference column 6 is empty")
            return assocparser.ParseResult(line, [], True)

        self._validate_id(evidence, split_line)

        interacting_taxon = None if interacting_taxon_id == "" else interacting_taxon_id
        if interacting_taxon != None:
            interacting_taxon = self._taxon_id(interacting_taxon_id, split_line)
            if interacting_taxon == None:
                self.report.error(line, assocparser.Report.INVALID_TAXON, interacting_taxon_id,
                                    msg="Taxon ID is invalid")
                return assocparser.ParseResult(line, [], True)

        #TODO: ecomap is currently one-way only
        #ecomap = self.config.ecomap
        #if ecomap != None:
        #    if ecomap.ecoclass_to_coderef(evidence) == (None,None):
        #        self.report.error(line, Report.UNKNOWN_EVIDENCE_CLASS, evidence,
        #                          msg="Expecting a known ECO class ID")

        ## --
        ## qualifier
        ## --
        negated, relation, other_qualifiers = self._parse_qualifier(qualifier, None)


        # Reference Column
        references = self.validate_pipe_separated_ids(reference, split_line)
        if references == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)

        # With/From
        withfroms = self.validate_pipe_separated_ids(withfrom, split_line, empty_allowed=True, extra_delims=",")
        if withfroms == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)


        ## --
        ## parse annotation extension
        ## See appending in http://doi.org/10.1186/1471-2105-15-155
        ## --
        object_or_exprs = self._parse_full_extension_expression(annotation_xp, line=split_line)

        subject_symbol = id
        subject_fullname = id
        subject_synonyms = []
        if self.gpi is not None:
            gp = self.gpi.get(id, {})
            if gp is not {}:
                subject_symbol = gp["symbol"]
                subject_fullname = gp["name"]
                subject_synonyms = gp["synonyms"].split("|")

        assoc = {
            'source_line': line,
            'subject': {
                'id': id,
                'label': subject_symbol,
                'fullname': subject_fullname,
                'synonyms': subject_synonyms,
                'taxon': {
                    'id': interacting_taxon
                },
            },
            'object': {
                'id':goid
            },
            'negated': negated,
            'relation': {
                'id': relation
            },
            'interacting_taxon': interacting_taxon,
            'evidence': {
                'type': evidence,
                'with_support_from': withfroms,
                'has_supporting_reference': references
            },
            'subject_extensions': [],
            'object_extensions': {},
            'aspect': self.compute_aspect(goid),
            'provided_by': assigned_by,
            'date': date,
        }
        if len(other_qualifiers) > 0:
            assoc['qualifiers'] = other_qualifiers
        if object_or_exprs is not None and len(object_or_exprs) > 0:
            assoc['object_extensions'] = {'union_of': object_or_exprs}


        return assocparser.ParseResult(line, [assoc], False)

    def is_header(self, line):
        return line.startswith("!")
