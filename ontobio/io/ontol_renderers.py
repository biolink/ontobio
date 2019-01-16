"""
Various classes for rendering of ontology graphs
"""

import networkx as nx
from networkx.drawing.nx_pydot import write_dot
import tempfile
import os
import subprocess
import json
import logging

class GraphRendererConfig():
    """
    configuration parameters
    """
    def __init__(self,
                 relsymbolmap=None,
                 show_text_definition=False):
        self.relsymbolmap = relsymbolmap
        self.show_text_definition = show_text_definition
        if self.relsymbolmap is None:
            self.relsymbolmap = {
                     'subClassOf': '%',
                     'subPropertyOf': '%',
                     'BFO:0000050': '<',
                     'RO:0002202': '~',
            }
        

class GraphRenderer():
    """
    base class for writing networkx graphs
    """
    def __init__(self,
                 outfile=None,
                 config=None,
                 **args):
        self.outfile = outfile
        if config is None:
            config = GraphRendererConfig()
        self.config = config
        
    
    def render(self, ontol, **args):
        """
        Render a `ontology` object
        """
        pass

    def write(self, ontol, **args):
        """
        Write a `ontology` object
        """
        s = self.render(ontol, **args)
        if self.outfile is None:
            print(s)
        else:
            f = open(self.outfile, 'w')
            f.write(s)
            f.close()

    def render_subgraph(self, ontol, nodes, **args):
        """
        Render a `ontology` object after inducing a subgraph
        """
        subont = ontol.subontology(nodes, **args)
        return self.render(subont, **args)
    
    def write_subgraph(self, ontol, nodes, **args):
        """
        Write a `ontology` object after inducing a subgraph
        """
        subont = ontol.subontology(nodes, **args)
        self.write(subont, **args)

    def render_relation(self, r, **args):
        """
        Render an object property
        """
        if r is None:
            return "."
        m = self.config.relsymbolmap
        if r in m:
            return m[r]
        return r
    
    def render_noderef(self, ontol, n, query_ids=None, **args):
        """
        Render a node object
        """
        if query_ids is None:
            query_ids = []
        marker = ""
        if n in query_ids:
            marker = " * "
        label = ontol.label(n)
        s = None
        if label is not None:
            s = '{} ! {}{}'.format(n,
                                   label,
                                   marker)
        else:
            s = str(n)
        if self.config.show_text_definition:
            td = ontol.text_definition(n)
            if td:
                s += ' "{}"'.format(td.val)
        return s
        
    @staticmethod
    def create(fmt):
        """
        Creates a GraphRenderer
        """
        w = None
        if fmt == 'tree':
            w = AsciiTreeGraphRenderer()
        elif fmt == 'dot':
            w = DotGraphRenderer(image_format='dot')
        elif fmt == 'png':
            w = DotGraphRenderer(image_format='png')
        elif fmt == 'ndot':
            w = NativeDotGraphRenderer()
        elif fmt == 'obo':
            w = OboFormatGraphRenderer()
        elif fmt == 'obog':
            w = OboJsonGraphRenderer()
        else:
            w = SimpleListGraphRenderer()
        return w
        
class NativeDotGraphRenderer(GraphRenderer):
    """
    writes as dot (graphviz format) files
    """
    def __init__(self, **args):
        super().__init__(**args)

    def render(self, ontol, **args):
        g = ontol.get_graph()
        _, fn = tempfile.mkstemp(suffix='dot')
        write_dot(g, fn)
        f = open(fn, 'r')
        s = f.read()
        f.close()
        return s

    def write(self, ontol, **args):
        g = ontol.get_graph()        
        fn = self.outfile
        if fn is None:
            _, fn = tempfile.mkstemp(suffix='dot')
        write_dot(g, fn)
        if self.outfile is None:
            f = open(fn, 'r')
            print(f.read())
            f.close()
            os.remove(fn)

class DotGraphRenderer(GraphRenderer):
    """
    uses js lib to generate png from dot

    This requires you install the node package [obographsviz](https://github.com/cmungall/obographviz)
    """
    def __init__(self,
                 image_format='png',
                 **args):
        super().__init__(**args)
        self.image_format = image_format
        # obographviz makes use of OboJson, so we leverage this here
        self.ojgr = OboJsonGraphRenderer(**args)

    # TODO: currently render and write are equivalent
    def render(self, ontol, query_ids=None, container_predicates=None, **args):
        if query_ids is None:
            query_ids = []
        if container_predicates is None:
            container_predicates = []
        g = ontol.get_graph()
        # create json object to pass to og2dot
        _, fn = tempfile.mkstemp(suffix='.json')
        self.ojgr.outfile = fn
        self.ojgr.write(ontol, **args)

        # call og2dot
        cmdtoks = ['og2dot.js']
        for q in query_ids:
            cmdtoks.append('-H')
            cmdtoks.append(q)
        cmdtoks.append('-t')
        cmdtoks.append(self.image_format)
        if len(container_predicates) > 0:
            for p in container_predicates:
                cmdtoks.append('-c')
                cmdtoks.append(p)
        if self.outfile is not None:
            cmdtoks.append('-o')
            cmdtoks.append(self.outfile)
        cmdtoks.append(fn)
        cp = subprocess.run(cmdtoks, check=True)
        logging.info(cp)
        os.remove(fn)
        
    def write(self, ontol, **args):
        self.render(ontol, **args)
            

class SimpleListGraphRenderer(GraphRenderer):
    """
    renders a graph as a simple flat list of nodes
    """
    def __init__(self, **args):
        super().__init__(**args)

    def render(self, ontol, **args):
        s = ""
        for n in ontol.nodes():
            s += self.render_noderef(ontol, n, **args) + "\n"
            #for n2 in ontol.parents(n):
            #    for _,ea in g.get_edge_data(n2,n).items():
            #        s += '  {} {}'.format(str(ea['pred']), self.render_noderef(ontol, n2, **args))
            #        s += "\n"
        return s
        
class AsciiTreeGraphRenderer(GraphRenderer):
    """
    Denormalized indented-text tree rendering
    """
    def __init__(self, **args):
        super().__init__(**args)
        
    def render(self, ontol, **args):
        #g = ontol.get_graph()
        #ts = nx.topological_sort(g)
        #roots = [n for n in ts if len(g.predecessors(n))==0]
        roots = ontol.get_roots()
        logging.info("Drawing ascii tree, using roots: {}".format(roots))
        if len(roots) == 0:
            logging.error("No roots in {}".format(ontol))
        s=""
        for n in roots:
            s += self._show_tree_node(None, n, ontol, 0, path=[], **args) + "\n"
        return s

    def _show_tree_node(self, rel, n, ontol, depth=0, path=None, **args):
        if path is None:
            path = []
        g = ontol.get_graph() # TODO - use ontol methods directly
        s = " " * depth + self.render_relation(rel) + " " +self.render_noderef(ontol, n, **args)
        if n in path:
            logging.warn("CYCLE: {} already visited in {}".format(n, path))
            return s + " <-- CYCLE\n"
        s += "\n"
        for c in ontol.children(n):
            preds = []
            for _,ea in g.get_edge_data(n,c).items():
                preds.append(ea['pred'])
            s+= self._show_tree_node(",".join(preds), c, ontol, depth+1, path+[n], **args)
        return s

class OboFormatGraphRenderer(GraphRenderer):
    """
    Render as obo format.

    Note this is currently incomplete
    """
    def __init__(self, **args):
        super().__init__(**args)
        
    def render(self, ontol, **args):
        ts = [n for n in ontol.nodes()]
        ts.sort()
        s = "ontology: auto\n\n"
        for n in ts:
            s += self.render_node(n, ontol, **args)
        return s
    
    def render_node(self, nid, ontol, **args):
        st = 'Term'
        if ontol.node_type == 'PROPERTY':
            st = 'Typedef'
            
        s = "[{}]\n".format(st)
        s += self.tag('id', nid)
        label = ontol.label(nid)
        if label is not None:
            s += self.tag('name', label)
            
        for p in ontol.parents(nid):
            for pred in ontol.child_parent_relations(nid,p):
                p_str = p
                if p in ontol.nodes():
                    p_label = ontol.label(p)
                    if p_label is not None:
                        p_str = '{} ! {}'.format(p, p_label)
                    
                if pred == 'subClassOf':
                    s += self.tag('is_a', p_str)
                else:
                    s += self.tag('relationship', pred, p_str)
        for ld in ontol.logical_definitions(nid):
            for gen in ld.genus_ids:
                s += self.tag('intersection_of', gen)
            for pred,filler in ld.restrictions:
                s += self.tag('intersection_of', pred, filler)

        td = ontol.text_definition(nid)
        if td:
            x = ""
            if td.xrefs is not None:
                x = ", ".join(td.xrefs)
            s += 'def: "{}" [{}]\n'.format(self._escape_quotes(td.val),x)
        else:
            logging.debug("No text def for: {}".format(nid))    

        logging.info("Looking up xrefs for {}".format(nid))
        for xref in ontol.xrefs(nid):
            s += "xref: {}\n".format(xref)

        if ontol.is_obsolete(nid):
            s += "is_obsolete: true\n"
            # TODO: consider links
            
        for syn in ontol.synonyms(nid):
            t = ""
            if syn.lextype is not None:
                t = " "+syn.lextype
            x = ""
            if syn.xrefs is not None:
                x = ", ".join(syn.xrefs)
            s += 'synonym: "{}" {}{} [{}]\n'.format(self._escape_quotes(syn.val),
                                                    syn.scope(),
                                                    t,
                                                    x)
        s += "\n"
        return s

    def _escape_quotes(self, v):
        # TODO: escape newlines etc
        return v.replace('"',"z").replace("\n", " ")
        
    # TODO
    def render_xrefs(self, nid, ontol, **args):
        g = ontol.xref_graph # TODO - use ontol methods directly
        n = g.node[nid]
        s = "[Term]\n"
        s += self.tag('id ! TODO', nid)
        s += self.tag('name', n['label'])
        for p in g.predecessors(nid):
            for _,ea in g.get_edge_data(p,nid).items():
                pred = ea['pred']
                if p in g and 'label' in g.node[p]:
                    p = '{} ! {}'.format(p, g.node[p]['label'])
                if pred == 'subClassOf':
                    s += self.tag('is_a', p)
                else:
                    s += self.tag('relationship', pred, p)
        s += "\n"
        return s
    
    def tag(self, t, *vs):
        v = " ".join(vs)
        return t + ': ' + v + "\n"

    # tag using dictionary
    def _dtag(self, t, d, k):
        if k in d:
            return self.tag(t, d[k])
        return ""
    
class OboJsonGraphRenderer(GraphRenderer):
    """
    Render as obographs json
    """
    def __init__(self, **args):
        super().__init__(**args)
        
    def to_json(self, ontol, **args):
        ontol.inline_xref_graph()
        g = ontol.get_graph() # TODO - use ontol methods directly
        obj = {}
        node_objs = []
        for n in ontol.nodes():
            node_objs.append(self.node_to_json(n, ontol, **args))
        obj['nodes'] = node_objs
        edge_objs = []
        for e in g.edges(data=True):
            edge_objs.append(self.edge_to_json(e, ontol, **args))
        obj['edges'] = edge_objs

        return {'graphs' : [obj]}

    def render(self, ontol, **args):
        obj = self.to_json(ontol, **args)
        return json.dumps(obj)
    
    def node_to_json(self, nid, ontol, **args):
        label = ontol.label(nid)
        if "include_meta" not in args or args['include_meta']:
            return {'id' : nid,
                    'lbl' : label,
                    'meta': ontol.node(nid).get('meta')}
        else:
            return {'id' : nid,
                'lbl' : label}
    
    def edge_to_json(self, e, ontol, **args):
        (obj,sub,meta) = e
        return {'sub' : sub,
                'obj' : obj,
                'pred' : meta['pred']}

    def tag(self, t, *vs):
        v = " ".join(vs)
        return t + ': ' + v + "\n"
    
