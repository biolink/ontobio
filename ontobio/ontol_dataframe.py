from ontobio import Ontology
import pandas as pd
import numpy as np

def make_ontology_dataframe(onts=None,
                            ont_map=None,
                            xref_prefixes=[],
                            relations=[]):
    items = []

    # create a map
    if ont_map is None:
        ont_map = {}
        for ont in onts:
            ont_map[ont.id] = ont
            
    for ont_id, ont in ont_map.items():
        for nid in ont.nodes():
            n = ont.node(nid)
            tdobj = ont.text_definition(nid)
            if tdobj is None:
                td = ''
            else:
                td = tdobj.val
            xrefs = ont.xrefs(nid)
            isa_parents = ont.parents(nid, relations=['subClassOf'])
            isa_children = ont.children(nid, relations=['subClassOf'])
            parents = ont.parents(nid)
            children = ont.children(nid)
            syns = [s.val for s in ont.synonyms(nid)]
            item = {
                'id': nid,
                'label': ont.label(nid),
                'type' : n.get('type'),
                'prefix': ont.prefix(nid),
                'ontology': ont_id,
                'children': children,
                'children_count': len(children),
                'parents': parents,
                'parent_count': len(parents),
                'isa_parents': isa_parents,
                'isa_parent_count': len(isa_parents),
                'isa_children': isa_children,
                'isa_children_count': len(isa_children),
                'synonyms': syns,
                'synonym_count': len(syns),
                'parent_count': len(parents),
                'xrefs': xrefs,
                'xref_count': len(xrefs),
                'text_definition': td

            }
            for p in xref_prefixes:
                p_xrefs = [x for x in xrefs if ont.prefix(x) == p]
                item['xrefs_'+p] = p_xrefs
                item['count_xrefs_'+p] = len(p_xrefs)
            for r in relations:
                r_parents = ont.parents(relations=[r])
                rn = ont.label(r, id_if_null=True)
                item['parents_'+rn] = r_parents
                item['count_parents_'+rn] = len(r_parents)
            
            # TODO: xrefs by src
            items.append(item)
    return pd.DataFrame(items)
