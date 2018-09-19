from ontobio.sparql.sparql_ontol_utils import SEPARATOR

def correctGOID(self, goid):
    return goid.replace(":", "_")

def correctGOCAM(self, gocam):
    if gocam.find('/') != -1:
        gocam = gocam[gocam:gocam.rfind('/') + 1]
    if not gocam.startsWith('gomodel'):
        gocam = 'gomodel:' + gocam.strip()
    return gocam

def correctGOCAMs(self, gocams):
    list = []
    for gocam in gocams:
        list.append(correctGOCAM(self, gocam))
    return list


def goSummary(self, goid):
    goid = correctGOID(self, goid)
    return """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX definition: <http://purl.obolibrary.org/obo/IAO_0000115>
    PREFIX obo: <http://www.geneontology.org/formats/oboInOwl#>

    SELECT ?goid ?label ?definition ?comment ?creation_date		(GROUP_CONCAT(distinct ?synonym;separator='""" + SEPARATOR + """') as ?synonyms)
                                                                (GROUP_CONCAT(distinct ?relatedSynonym;separator='""" + SEPARATOR + """') as ?relatedSynonyms)
                                                                (GROUP_CONCAT(distinct ?alternativeId;separator='""" + SEPARATOR + """') as ?alternativeIds)
                                                                (GROUP_CONCAT(distinct ?xref;separator='""" + SEPARATOR + """') as ?xrefs)
                                                                (GROUP_CONCAT(distinct ?subset;separator='""" + SEPARATOR + """') as ?subsets)

    WHERE {
        BIND(<http://purl.obolibrary.org/obo/""" + goid + """> as ?goid) .
        optional { ?goid rdfs:label ?label } .
        optional { ?goid definition: ?definition } .
        optional { ?goid rdfs:comment ?comment } .
        optional { ?goid obo:creation_date ?creation_date } .
        optional { ?goid obo:hasAlternativeId ?alternativeId } .
        optional { ?goid obo:hasRelatedSynonym ?relatedSynonym } .
        optional { ?goid obo:hasExactSynonym ?synonym } .
        optional { ?goid obo:hasDbXref ?xref } .
        optional { ?goid obo:inSubset ?subset } .
    }
    GROUP BY ?goid ?label ?definition ?comment ?creation_date
    """

def goHierarchy(self, goid):
    goid = correctGOID(self, goid)
    return """   
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX definition: <http://purl.obolibrary.org/obo/IAO_0000115>
    SELECT ?hierarchy ?GO ?label WHERE {
        BIND(<http://purl.obolibrary.org/obo/""" + goid + """> as ?goquery)
        {
            {
                ?goquery rdfs:subClassOf+ ?GO .
                ?GO rdfs:label ?label .
                FILTER (LANG(?label) != "en")    
                BIND("parent" as ?hierarchy)
            }
            UNION
            {
                ?GO rdfs:subClassOf* ?goquery .
                ?GO rdfs:label ?label .    		
                FILTER (LANG(?label) != "en")    
                BIND(IF(?goquery = ?GO, "query", "child") as ?hierarchy) .
            }
        }
    }  
    """


def gocams(self, states, start = None, rows = None):
    statesList = ""

    for docState in states:
        statesList += "\"" + docState.value + "\"^^xsd:string "

    query = """
    PREFIX metago: <http://model.geneontology.org/>
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
    PREFIX obo: <http://www.geneontology.org/formats/oboInOwl#>
    PREFIX providedBy: <http://purl.org/pav/providedBy>

    SELECT  ?gocam ?date ?state ?title (GROUP_CONCAT(?orcid;separator='""" + SEPARATOR + """') AS ?orcids) 
                                (GROUP_CONCAT(?name;separator='""" + SEPARATOR + """') AS ?names)
                                (GROUP_CONCAT(distinct ?providedBy;separator='""" + SEPARATOR + """') AS ?groupids) 
                                (GROUP_CONCAT(distinct ?providedByLabel;separator='""" + SEPARATOR + """') AS ?groupnames) 
    
    WHERE 
    {
        {
            VALUES ?state { """ + statesList + """ }
            GRAPH ?gocam {            
                ?gocam metago:graphType metago:noctuaCam .
                ?gocam <http://geneontology.org/lego/modelstate> ?state .
                ?gocam dc:title ?title ;
                     dc:date ?date ;
                     dc:contributor ?orcid .
                BIND( IRI(?orcid) AS ?orcidIRI ).
            }
     
            optional { ?orcidIRI rdfs:label ?name }
            BIND(IF(bound(?name), ?name, ?orcid) as ?name) .
        }
      
        optional {
            GRAPH ?gocam {
                ?gocam providedBy: ?providedBy .
                BIND( IRI(?providedBy) AS ?providedByIRI ).
            }
            ?providedByIRI rdfs:label ?providedByLabel .
        }   
      
    }
    GROUP BY ?gocam ?date ?title ?state
    ORDER BY DESC(?date)
    """
    if start is not None and rows is not None:
        query += """LIMIT """ + str(rows) + """
                    OFFSET """ + str(start)
    return query


def gocamsWithGO(self, goid):
    goid = correctGOID(self, goid)
    return """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX metago: <http://model.geneontology.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT distinct ?gocam
    WHERE 
    {
        GRAPH ?gocam {
            ?gocam metago:graphType metago:noctuaCam .    
            ?entity rdf:type owl:NamedIndividual .
            ?entity rdf:type ?goid .
            FILTER(?goid = <http://purl.obolibrary.org/obo/""" + goid + """>)
        }
    }
    """

def gocamsWithPMID(self, pmid):
    return """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX metago: <http://model.geneontology.org/>

    SELECT distinct ?gocam
    WHERE 
    {
        GRAPH ?gocam {
            ?gocam metago:graphType metago:noctuaCam .    	
            ?s dc:source ?source .
            BIND(REPLACE(?source, " ", "") AS ?source) .
            FILTER((CONTAINS(?source, """ + pmid + """)))
        }           
    }
    """

def gocamsWithGP(self, gpid):
    return """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> 
    PREFIX metago: <http://model.geneontology.org/>
    PREFIX enabled_by: <http://purl.obolibrary.org/obo/RO_0002333>
    
    SELECT distinct ?gocam
    WHERE 
    {  
      GRAPH ?gocam {
        ?gocam metago:graphType metago:noctuaCam .    
        ?s enabled_by: ?gpnode .    
        ?gpnode rdf:type ?identifier .
        FILTER(?identifier = <""" + gpid + """>) .         
      } 
    }
    """







def gocamsGO(self, gocams):
    gocams = correctGOCAMs(self, gocams)

    return """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX metago: <http://model.geneontology.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX definition: <http://purl.obolibrary.org/obo/IAO_0000115>
    PREFIX BP: <http://purl.obolibrary.org/obo/GO_0008150>
    PREFIX MF: <http://purl.obolibrary.org/obo/GO_0003674>
    PREFIX CC: <http://purl.obolibrary.org/obo/GO_0005575>

    SELECT distinct ?gocam ?goclasses ?goids ?gonames ?definitions
    WHERE 
    {
        VALUES ?gocam { """ + gocams + """}
#		    VALUES ?gocam { <http://model.geneontology.org/5a7e68a100001298> <http://model.geneontology.org/5a7e68a100001201> <http://model.geneontology.org/5a7e68a100001125> <http://model.geneontology.org/5a7e68a100000655>}

        GRAPH ?gocam {
            ?entity rdf:type owl:NamedIndividual .
            ?entity rdf:type ?goids
        }

        VALUES ?goclasses { BP: MF: CC:  } . 
        ?goids rdfs:subClassOf+ ?goclasses .
        ?goids rdfs:label ?gonames .
        ?goids definition: ?definitions .
    }
    ORDER BY DESC(?gocam)
    """




def userMeta(self, orcid):
    return """
    PREFIX metago: <http://model.geneontology.org/>
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
    PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>
    PREFIX has_affiliation: <http://purl.obolibrary.org/obo/ERO_0000066> 
    PREFIX enabled_by: <http://purl.obolibrary.org/obo/RO_0002333>
    PREFIX obo: <http://www.geneontology.org/formats/oboInOwl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX BP: <http://purl.obolibrary.org/obo/GO_0008150>
    PREFIX MF: <http://purl.obolibrary.org/obo/GO_0003674>
    PREFIX CC: <http://purl.obolibrary.org/obo/GO_0005575>

    SELECT  ?name  			(GROUP_CONCAT(distinct ?organization;separator='""" + SEPARATOR + """') AS ?organizations) 
                            (GROUP_CONCAT(distinct ?affiliationIRI;separator='""" + SEPARATOR + """') AS ?affiliationsIRI) 
                            (GROUP_CONCAT(distinct ?affiliation;separator='""" + SEPARATOR + """') AS ?affiliations) 
                            (GROUP_CONCAT(distinct ?gocam;separator='""" + SEPARATOR + """') as ?gocams)
                            (GROUP_CONCAT(distinct ?date;separator='""" + SEPARATOR + """') as ?gocamsDate)
                            (GROUP_CONCAT(distinct ?title;separator='""" + SEPARATOR + """') as ?gocamsTitle)
                            (GROUP_CONCAT(distinct ?goid;separator='""" + SEPARATOR + """') as ?bpids)
                            (GROUP_CONCAT(distinct ?goname;separator='""" + SEPARATOR + """') as ?bpnames)
                            (GROUP_CONCAT(distinct ?gpid;separator='""" + SEPARATOR + """') as ?gpids)
                            (GROUP_CONCAT(distinct ?gpname;separator='""" + SEPARATOR + """') as ?gpnames)
    WHERE 
    {
        #BIND(""" + orcid + """ as ?orcid) .
        #BIND("SynGO:SynGO-pim"^^xsd:string as ?orcid) .
        BIND("http://orcid.org/0000-0001-7476-6306"^^xsd:string as ?orcid)
        #BIND("http://orcid.org/0000-0003-1074-8103"^^xsd:string as ?orcid) .

        BIND(IRI(?orcid) as ?orcidIRI) .


        # Getting some information on the model
        GRAPH ?gocam 
        {
            ?gocam 	metago:graphType metago:noctuaCam ;
                    dc:date ?date ;
                    dc:title ?title ;
                    dc:contributor ?orcid .

            ?entity rdf:type owl:NamedIndividual .
            ?entity rdf:type ?goid .

            ?s enabled_by: ?gpentity .    
            ?gpentity rdf:type ?gpid .
            FILTER(?gpid != owl:NamedIndividual) .
        }


        VALUES ?GO_class { BP: } . 
        # rdf:type faster then subClassOf+ but require filter 			
        # ?goid rdfs:subClassOf+ ?GO_class .
        ?entity rdf:type ?GO_class .

        # Filtering out the root BP, MF & CC terms
        filter(?goid != MF: )
        filter(?goid != BP: )
        filter(?goid != CC: )

        ?goid rdfs:label ?goname .

        # Getting some information on the contributor
        optional { ?orcidIRI rdfs:label ?name } .
        BIND(IF(bound(?name), ?name, ?orcid) as ?name) .
        optional { ?orcidIRI vcard:organization-name ?organization } .
        optional { 
            ?orcidIRI has_affiliation: ?affiliationIRI .
            ?affiliationIRI rdfs:label ?affiliation
        } .

        # crash the query for SYNGO user "http://orcid.org/0000-0002-1190-4481"^^xsd:string  
        optional {
        ?gpid rdfs:label ?gpname .
        }
        BIND(IF(bound(?gpname), ?gpname, ?gpid) as ?gpname)

    }
    GROUP BY ?name    
    """


def goSubsets(self, goid):
    goid = correctGOID(self, goid)
    return """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX obo: <http://www.geneontology.org/formats/oboInOwl#>

    SELECT ?label ?subset

    WHERE {
        BIND(<http://purl.obolibrary.org/obo/""" + goid + """> as ?goid) .
        optional { ?goid obo:inSubset ?subset .
                   ?subset rdfs:comment ?label } .
    }
    """

def subsetIdIRI(self, subsetid):
    return "http://purl.obolibrary.org/obo/go#" + subsetid

def subset(self, subsetid):
    subseturi = subsetIdIRI(self, subsetid)
    return """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX obo: <http://www.geneontology.org/formats/oboInOwl#>

    SELECT ?goid ?label
    WHERE {
        BIND(<""" + subseturi + """> as ?subset) .  
	  	?goid obo:inSubset ?subset .
  		?goid rdfs:label ?label .
		FILTER (lang(?label) != "en")
    }
    """