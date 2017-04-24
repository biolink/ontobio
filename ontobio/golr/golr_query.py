
class GolrServer():
    pass


class GolrQuery():
    def __init__(self,
                 subject_category=None,
                 object_category=None,
                 relation=None,
                 subject=None,
                 subjects=None,
                 object=None,
                 objects=None,
                 subject_direct=False,
                 subject_taxon=None,
                 object_taxon=None,
                 invert_subject_object=None,
                 use_compact_associations=False,
                 include_raw=False,
                 field_mapping=None,
                 solr=monarch_solr,
                 select_fields=None,
                 fetch_objects=False,
                 fetch_subjects=False,
                 fq={},
                 slim=[],
                 json_facet=None,
                 iterate=False,
                 map_identifiers=None,
                 facet_fields = [
                     M.SUBJECT_TAXON_LABEL,
                     M.OBJECT_CLOSURE
                 ],
                 facet_field_limits = None,
                 facet_limit=25,
                 facet_mincount=1,
                 facet_pivot_fields = [],
                 facet_on = 'on',
                 rows=10,
                 **kwargs):

        """Fetch a set of association objects based on a query.

        Arguments
        ---------

        fetch_objects : bool

        we frequently want a list of distinct association objects (in
        the RDF sense).  for example, when querying for all phenotype
        associations for a gene, it is convenient to get a list of
        distinct phenotype terms. Although this can be obtained by
        iterating over the list of associations, it can be expensive
        to obtain all associations.

        Results are in the 'objects' field

        fetch_subjects : bool

        This is the analog of the fetch_objects field. Note that due
        to an inherent asymmetry by which the list of subjects can be
        very large (e.g. all genes in all species for "metabolic
        process" or "metabolic phenotype") it's necessary to combine
        this with subject_category and subject_taxon filters

        Results are in the 'subjects' field

        slim : List

        a list of either class ids (or in future subset ids), used to
        map up (slim) objects in associations. This will populate
        an additional 'slim' field in each association object corresponding
        to the slimmed-up value(s) from the direct objects.
        If fetch_objects is passed, this will be populated with slimmed IDs.

        evidence: String

        Evidence class from ECO. Inference is used.

        exclude_automatic_assertions : bool

        If true, then any annotations with evidence of ECO:0000501 (IEA) or
        subclasses will be excluded.

        use_compact_associations : bool

        If true, then the associations list will be false, instead
        compact_associations contains a more compact representation
        consisting of objects with (subject, relation and objects)

        """
        self.subject_category=subject_category,
        self.object_category=object_category,
        self.relation=relation,
        self.subject=subject,
        self.subjects=subjects,
        self.object=object,
        self.objects=objects,
        self.subject_direct=subject_direct,
        self.subject_taxon=subject_taxon,
        self.object_taxon=object_taxon,
        self.invert_subject_object=invert_subject_object,
        self.use_compact_associations=use_compact_associations,
        self.include_raw=include_raw,
        self.field_mapping=field_mapping,
        self.solr=solr,
        self.select_fields=select_fields,
        self.fetch_objects=fetch_objects,
        self.fetch_subjects=fetch_subjects,
        self.fq=fq,
        self.slim=slim,
        self.json_facet=json_facet,
        self.iterate=iterate,
        self.map_identifiers=map_identifiers,
        self.facet_fields=facet_fields,
        self.facet_field_limits=facet_field_limits,
        self.facet_limit=facet_limit,
        self.facet_mincount=facet_mincount,
        self.facet_pivot_fields=facet_pivot_fields,
        self.facet_on=facet_on,
        self.rows=row
        
    def adjust(self):
        pass

    # TODO: selfize
    def solr_params(self):
        # canonical form for MGI is a CURIE MGI:nnnn
        #if subject is not None and subject.startswith('MGI:MGI:'):
        #    logging.info('Unhacking MGI ID presumably from GO:'+str(subject))
        #    subject = subject.replace("MGI:MGI:","MGI")
        subject=self.subject
        if subject is not None:
            subject = make_canonical_identifier(subject)
        subjects=self.subjects
        if subjects is not None:
            subjects = [make_canonical_identifier(s) for s in subjects]
    
        # temporary: for querying go solr, map fields. TODO
        object_category=self.object_category
        logging.info("Object category: {}".format(object_category))
        object=self.object
        if object_category is None and object is not None and object.startswith('GO:'):
            object_category = 'function'
            logging.info("Inferring Object category: {}".format(object_category))
            
        if object_category is not None and object_category == 'function':
            ## TODO - check scope
            solr=self.solr
            go_golr_url = "http://golr.berkeleybop.org/solr/"
            solr = pysolr.Solr(go_golr_url, timeout=5)
            ## TODO - check scope
            field_mapping=self.field_mapping
            field_mapping=goassoc_fieldmap()
            ## TODO - check scope
            fq=self.fq
            fq['document_category'] = 'annotation'
            if subject is not None:
                subject = make_gostyle_identifier(subject)
            if subjects is not None:
                subjects = [make_gostyle_identifier(s) for s in subjects]
    
        subject_category=self.subject_category
        if subject_category is not None and subject_category == 'disease':
            ## TODO - check scope
            subject_taxon=self.subject_taxon
            if subject_taxon is not None and subject_taxon=='NCBITaxon:9606':
                logging.info("Unsetting taxon, until indexed correctly")
                subject_taxon = None
    
        invert_subject_object=self.invert_subject_object
        if invert_subject_object is None:
            # TODO: consider placing in a separate lookup
            p = (subject_category,object_category)
            if p == ('disease','gene'):
                invert_subject_object = True
            elif p == ('disease','model'):
                invert_subject_object = True
            else:
                invert_subject_object = False
            if invert_subject_object:
                logging.info("Inferred that subject/object should be inverted for {}".format(p))
                
        # typically information is stored one-way, e.g. model-disease;
        # sometimes we want associations from perspective of object
        if invert_subject_object:
            (subject,object) = (object,subject)
            (subject_category,object_category) = (object_category,subject_category)
            ## TODO - check scope
            object_taxon=self.object_taxon
            (subject_taxon,object_taxon) = (object_taxon,subject_taxon)
    
        use_compact_associations=self.use_compact_associations
        if use_compact_associations:
            ## TODO - check scope
            facet_fields=self.facet_fields
            facet_fields = []
            ## TODO - check scope
            facet_on=self.facet_on
            facet_on = 'off'
            ## TODO - check scope
            facet_limit=self.facet_limit
            facet_limit = 0
            ## TODO - check scope
            select_fields=self.select_fields
            select_fields = [
                M.SUBJECT,
                M.SUBJECT_LABEL,
                M.RELATION,
                M.OBJECT]
    
        if subject_category is not None:
            fq['subject_category'] = subject_category
        if object_category is not None:
            fq['object_category'] = object_category
    
    
        if object is not None:
            # TODO: make configurable whether to use closure
            fq['object_closure'] = object
        if subject is not None:
            # note: by including subject closure by default,
            # we automaticaly get equivalent nodes
            ## TODO - check scope
            subject_direct=self.subject_direct
            if subject_direct:
                fq['subject'] = subject
            else:
                fq['subject_closure'] = subject
        if subjects is not None:
            # lists are assumed to be disjunctive
            if subject_direct:
                fq['subject'] = subjects
            else:
                fq['subject_closure'] = subjects
        objects=self.objects
        if objects is not None:
            # lists are assumed to be disjunctive
            fq['object_closure'] = objects
        relation=self.relation
        if relation is not None:
            fq['relation_closure'] = relation
        if subject_taxon is not None:
            fq['subject_taxon_closure'] = subject_taxon
        if 'id' in kwargs:
            fq['id'] = kwargs['id']
        if 'evidence' in kwargs and kwargs['evidence'] is not None:
            e = kwargs['evidence']
            if e.startswith("-"):
                fq['-evidence_object_closure'] = e.replace("-","")
            else:
                fq['evidence_object_closure'] = e
                
        if 'exclude_automatic_assertions' in kwargs and kwargs['exclude_automatic_assertions']:
            fq['-evidence_object_closure'] = 'ECO:0000501'
        if 'pivot_subject_object' in kwargs and kwargs['pivot_subject_object']:
            ## TODO - check scope
            facet_pivot_fields=self.facet_pivot_fields
            facet_pivot_fields = [M.SUBJECT, M.OBJECT]
    
    
        # Map solr field names for fq. The generic Monarch schema is
        # canonical, GO schema is mapped to this using
        # field_mapping dictionary
        if field_mapping is not None:
            for (k,v) in field_mapping.items():
    
                # map fq[k] -> fq[k]
                if k in fq:
                    if v is None:
                        del fq[k]
                    else:
                        fq[v] = fq[k]
                        del fq[k]
    
                # in solr, the fq field can be
                # a negated expression, e.g. -evidence_object_closure:"ECO:0000501"
                # ideally we would have a higher level representation rather than
                # relying on string munging...
                negk = '-' + k
                if negk in fq:
                    if v is None:
                        del fq[negk]
                    else:
                        negv = '-' + v
                        fq[negv] = fq[negk]
                        del fq[negk]
    
        filter_queries = []
        qstr = "*:*"
        filter_queries = [ '{}:{}'.format(k,solr_quotify(v)) for (k,v) in fq.items()]
    
        # unless caller specifies a field list, use default
        if select_fields is None:
            select_fields = [
                M.ID,
                M.IS_DEFINED_BY,
                M.SOURCE,
                M.SUBJECT,
                M.SUBJECT_LABEL,
                M.SUBJECT_TAXON,
                M.SUBJECT_TAXON_LABEL,
                M.RELATION,
                M.RELATION_LABEL,
                M.OBJECT,
                M.OBJECT_LABEL,
            ]
            if 'unselect_evidence' not in kwargs or not kwargs['unselect_evidence']:
                select_fields += [
                    M.EVIDENCE_OBJECT,
                    M.EVIDENCE_GRAPH
                ]
    
        map_identifiers=self.map_identifiers
        if map_identifiers is not None:
            select_fields.append(M.SUBJECT_CLOSURE)
    
        slim=self.slim
        if slim is not None and len(slim)>0:
            select_fields.append(M.OBJECT_CLOSURE)
    
        if field_mapping is not None:
            logging.info("Applying field mapping to SELECT: {}".format(field_mapping))
            select_fields = [ map_field(fn, field_mapping) for fn in select_fields ]
    
    
        facet_fields = [ map_field(fn, field_mapping) for fn in facet_fields ]
    
        #logging.info('FL'+str(select_fields))
        is_unlimited = False
        rows=self.rows
        if rows < 0:
            is_unlimited = True
            ## TODO - check scope
            iterate=self.iterate
            iterate = True
            rows = MAX_ROWS
        params = {
            'q': qstr,
            'fq': filter_queries,
            'facet': facet_on,
            'facet.field': facet_fields,
            'facet.limit': facet_limit,
            ## TODO - check scope
            facet_mincount=self.facet_mincount
            'facet.mincount': facet_mincount,
            'fl': ",".join(select_fields),
            'rows': rows
        }
        json_facet=self.json_facet
        if json_facet:
            params['json.facet'] = json.dumps(json_facet)
    
        facet_field_limits=self.facet_field_limits
        if facet_field_limits is not None:
            for (f,flim) in facet_field_limits.items():
                params["f."+f+".facet.limit"] = flim
    
    
        if len(facet_pivot_fields) > 0:
            params['facet.pivot'] = ",".join(facet_pivot_fields)
            params['facet.pivot.mincount'] = 1
            
    def exec(self):
        logging.info("PARAMS="+str(params))
        results = solr.search(**params)
        n_docs = len(results.docs)
        logging.info("Docs found: {}".format(results.hits))
    
        if iterate:
            docs = results.docs
            start = n_docs
            while n_docs >= rows:
                logging.info("Iterating; start={}".format(start))
                next_results = solr.search(**params, start=start)
                next_docs = next_results.docs
                n_docs = len(next_docs)
                docs += next_docs
                start += rows
            results.docs = docs
    
    
    
        fcs = results.facets
    
        payload = {
            'facet_counts': translate_facet_field(fcs),
            'pagination': {}
        }
    
        include_raw=self.include_raw
        if include_raw:
            # note: this is not JSON serializable, do not send via REST
            payload['raw'] = results
    
        # TODO - check if truncated
    
        logging.info("COMPACT={} INV={}".format(use_compact_associations, invert_subject_object))
        if use_compact_associations:
            payload['compact_associations'] = translate_docs_compact(results.docs, field_mapping=field_mapping,
                                                                     slim=slim, invert_subject_object=invert_subject_object,
                                                                     map_identifiers=map_identifiers, **kwargs)
        else:
            payload['associations'] = translate_docs(results.docs, field_mapping=field_mapping, map_identifiers=map_identifiers, **kwargs)
    
        if 'facet_pivot' in fcs:
            payload['facet_pivot'] = fcs['facet_pivot']
        if 'facets' in results.raw_response:
            payload['facets'] = results.raw_response['facets']
    
        # For solr, we implement this by finding all facets
        # TODO: no need to do 2nd query, see https://wiki.apache.org/solr/SimpleFacetParameters#Parameters
        fetch_objects=self.fetch_objects
        if fetch_objects:
            core_object_field = M.OBJECT
            if slim is not None and len(slim)>0:
                core_object_field = M.OBJECT_CLOSURE
            object_field = map_field(core_object_field, field_mapping)
            if invert_subject_object:
                object_field = map_field(M.SUBJECT, field_mapping)
            oq_params = params.copy()
            oq_params['fl'] = []
            oq_params['facet.field'] = [object_field]
            oq_params['facet.limit'] = -1
            oq_params['rows'] = 0
            oq_params['facet.mincount'] = 1
            oq_results = solr.search(**oq_params)
            ff = oq_results.facets['facet_fields']
            ofl = ff.get(object_field)
            # solr returns facets counts as list, every 2nd element is number, we don't need the numbers here
            payload['objects'] = ofl[0::2]
    
        fetch_subjects=self.fetch_subjects
        if fetch_subjects:
            core_subject_field = M.SUBJECT
            if slim is not None and len(slim)>0:
                core_subject_field = M.SUBJECT_CLOSURE
            subject_field = map_field(core_subject_field, field_mapping)
            if invert_subject_object:
                subject_field = map_field(M.SUBJECT, field_mapping)
            oq_params = params.copy()
            oq_params['fl'] = []
            oq_params['facet.field'] = [subject_field]
            oq_params['facet.limit'] = MAX_ROWS
            oq_params['rows'] = 0
            oq_params['facet.mincount'] = 1
            oq_results = solr.search(**oq_params)
            ff = oq_results.facets['facet_fields']
            ofl = ff.get(subject_field)
            # solr returns facets counts as list, every 2nd element is number, we don't need the numbers here
            payload['subjects'] = ofl[0::2]
            if len(payload['subjects']) == MAX_ROWS:
                payload['is_truncated'] = True
    
        if slim is not None and len(slim)>0:
            if 'objects' in payload:
                payload['objects'] = [x for x in payload['objects'] if x in slim]
            if 'associations' in payload:
                for a in payload['associations']:
                    a['slim'] = [x for x in a['object_closure'] if x in slim]
                    del a['object_closure']
    
        return payload
            
    
