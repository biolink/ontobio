from ontobio.io.assocparser import AssocParser
from ontobio.io import assocparser
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION

class HpoaParser(AssocParser):
    """
    Parser for HPOA format

    http://human-phenotype-ontology.github.io/documentation.html#annot

    Note that there are similarities with Gaf format, so we inherit from GafParser, and override
    """

    def __init__(self,config=assocparser.AssocParserConfig()):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """

        self.config = config
        self.report = assocparser.Report(config=self.config)

    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) < 14:
                logging.error("Unexpected number of vals: {}.".format(vals))

            negated, relation, _ = self._parse_qualifier(vals[3], vals[8])

            # never include NOTs in a skim
            if negated:
                continue
            if self._is_exclude_relation(relation):
                continue
            id = self._pair_to_id(vals[0], vals[1])
            if not self._validate_id(id, line, context=ENTITY):
                continue
            n = vals[2]
            t = vals[4]
            tuples.append( (id,n,t) )
        return tuples

    def parse_line(self, line):
        """
        Parses a single line of a HPOA file

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
        config = self.config

        parsed = super().validate_line(line)
        if parsed:
            return parsed

        if self.is_header(line):
            return assocparser.ParseResult(line, [], False)

        # http://human-phenotype-ontology.github.io/documentation.html#annot
        vals = line.split("\t")
        if len(vals) != 14:
            self.report.error(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
                msg="There were {columns} columns found in this line, and there should be 14".format(columns=len(vals)))
            return assocparser.ParseResult(line, [], True)

        [db,
         db_object_id,
         db_object_symbol,
         qualifier,
         hpoid,
         reference,
         evidence,
         onset,
         frequency,
         withfrom,
         aspect,
         db_object_synonym,
         date,
         assigned_by] = vals

        # hardcode this, as HPOA is currently human-only
        taxon = 'NCBITaxon:9606'
        split_line = assocparser.SplitLine(line=line, values=vals, taxon=taxon)


        # hardcode this, as HPOA is currently disease-only
        db_object_type = 'disease'

        ## --
        ## db + db_object_id. CARD=1
        ## --
        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, split_line, context=ENTITY):
            return assocparser.ParseResult(line, [], True)

        if not self._validate_id(hpoid, split_line, context=ANNOTATION):
            return assocparser.ParseResult(line, [], True)

        valid_hpoid = self._validate_ontology_class_id(hpoid, split_line)
        if valid_hpoid == None:
            return assocparser.ParseResult(line, [], True)
        hpoid = valid_hpoid

        # validation
        #self._validate_symbol(db_object_symbol, line)

        #TODO: HPOA has different date styles
        #date = self._normalize_gaf_date(date, line)

        # Example use case: mapping from OMIM to Orphanet
        if config.entity_map is not None:
            id = self.map_id(id, config.entity_map)
            toks = id.split(":")
            db = toks[0]
            db_object_id = toks[1:]
            vals[1] = db_object_id

        ## --
        ## end of line re-processing
        ## --
        # regenerate line post-mapping
        line = "\t".join(vals)

        ## --
        ## db_object_synonym CARD=0..*
        ## --
        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []


        ## --
        ## qualifier
        ## --
        ## we generate both qualifier and relation field
        relation = None
        qualifiers = qualifier.split("|")
        if qualifier == '':
            qualifiers = []
        negated =  'NOT' in qualifiers
        other_qualifiers = [q for q in qualifiers if q != 'NOT']

        ## CURRENTLY NOT USED
        if len(other_qualifiers) > 0:
            relation = other_qualifiers[0]
        else:
            if aspect == 'O':
                relation = 'has_phenotype'
            elif aspect == 'I':
                relation = 'has_inheritance'
            elif aspect == 'M':
                relation = 'mortality'
            elif aspect == 'C':
                relation = 'has_onset'
            else:
                relation = None

        # With/From
        withfroms = self.validate_pipe_separated_ids(withfrom, split_line, empty_allowed=True, extra_delims=",")
        if withfroms == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)

        ## --
        ## hpoid
        ## --
        object = {'id':hpoid,
                  'taxon': taxon}

        # construct subject dict
        subject = {
            'id':id,
            'label':db_object_symbol,
            'type': db_object_type,
            'synonyms': synonyms,
            'taxon': {
                'id': taxon
            }
        }

        ## --
        ## evidence
        ## reference
        ## withfrom
        ## --
        evidence = {
            'type': evidence,
            'has_supporting_reference': reference.split("; "),
            'with_support_from': withfroms
        }

        ## Construct main return dict
        assoc = {
            'source_line': line,
            'subject': subject,
            'object': object,
            'negated': negated,
            'qualifiers': qualifiers,
            'relation': {
                'id': relation
            },
            'interacting_taxon': None,
            'evidence': evidence,
            'provided_by': assigned_by,
            'date': date,

        }

        return assocparser.ParseResult(line, [assoc], False)

    def is_header(self, line):
        return line.startswith("!")
