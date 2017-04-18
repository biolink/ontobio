"""
Various classes for rendering of networkx ontology graphs
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
                 relsymbolmap={
                     'subClassOf': '%',
                     'BFO:0000050': '<',
                     'RO:0002202': '~',
                 }):
        self.relsymbolmap = relsymbolmap
        

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
        
    
    def render(self, g, **args):
        """
        Render a networkx graph object
        """
        pass

    def write(self, g, **args):
        """
        Write a networkx graph object
        """
        s = self.render(g, **args)
        if self.outfile is None:
            print(s)
        else:
            f = open(self.outfile, 'w')
            f.write(s)
            f.close()

    def render_subgraph(self, g, nodes, **args):
        """
        Render a networkx graph object after inducing a subgraph
        """
        subg = g.subgraph(nodes)
        return self.render(subg, **args)
    
    def write_subgraph(self, g, nodes, **args):
        """
        Write a networkx graph object after inducing a subgraph
        """
        subg = g.subgraph(nodes)
        self.write(subg, **args)

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
    
    def render_noderef(self, g, n, query_ids=[], **args):
        """
        Render a node object
        """
        marker = ""
        if n in query_ids:
            marker = " * "
        if n in g.node and 'label' in g.node[n]:
            return '{} ! {}{}'.format(str(n),
                                      g.node[n]['label'],
                                      marker)
        else:
            return str(n)
        
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

    def render(self, g, **args):
        _, fn = tempfile.mkstemp(suffix='dot')
        write_dot(g, fn)
        f = open(fn, 'r')
        s = f.read()
        f.close()
        return s

    def write(self, g, **args):
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
        self.ojgr = OboJsonGraphRenderer(**args)

    # TODO: currently render and write are equivalent
    def render(self, g, query_ids=[], container_predicates=[], **args):
        # create json object to pass to og2dot
        _, fn = tempfile.mkstemp(suffix='.json')
        self.ojgr.outfile = fn
        self.ojgr.write(g, **args)

        # call og2dot
        cmdtoks = ['og2dot.js']
        if query_ids is not None:
            for q in query_ids:
                cmdtoks.append('-H')
                cmdtoks.append(q)
        cmdtoks.append('-t')
        cmdtoks.append(self.image_format)
        if container_predicates is not None and len(container_predicates)>0:
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
        
    def write(self, g, **args):
        self.render(g, **args)
            

class SimpleListGraphRenderer(GraphRenderer):
    """
    renders a graph as a simple flat list of nodes
    """
    def __init__(self, **args):
        super().__init__(**args)

    def render(self, g, **args):
        s = ""
        for n in g.nodes():
            s += self.render_noderef(g, n, **args) + "\n"
            for n2 in g.predecessors(n):
                for _,ea in g[n2][n].items():
                    s += '  {} {}'.format(str(ea['pred']), self.render_noderef(g, n2, **args))
                    s += "\n"
        return s
        
class AsciiTreeGraphRenderer(GraphRenderer):
    """
    Denormalized indented-text tree rendering
    """
    def __init__(self, **args):
        super().__init__(**args)
        
    def render(self, g, **args):
        ts = nx.topological_sort(g)
        roots = [n for n in ts if len(g.predecessors(n))==0]
        s=""
        for n in roots:
            s += self._show_tree_node(None, n, g, 0, **args) + "\n"
        return s

    def _show_tree_node(self, rel, n, g, depth=0, **args):
        s = " " * depth + self.render_relation(rel) + " " +self.render_noderef(g, n, **args) + "\n"
        for c in g.successors(n):
            preds = []
            for _,ea in g[n][c].items():
                preds.append(ea['pred'])
            s+= self._show_tree_node(",".join(preds), c, g, depth+1, **args)
        return s

class OboFormatGraphRenderer(GraphRenderer):
    """
    Render as obo format
    """
    def __init__(self, **args):
        super().__init__(**args)
        
    def render(self, g, **args):
        ts = nx.topological_sort(g)
        s = "ontology: auto\n\n"
        for n in ts:
            s += self.render_noderef(self, n, g, **args)
        return s

    def render(self, g, **args):
        ts = nx.topological_sort(g)
        s = "ontology: auto\n\n"
        for n in ts:
            s += self.render_node(n, g, **args)
        return s
    
    def render_node(self, nid, g, **args):
        n = g.node[nid]
        s = "[Term]\n";
        s += self.tag('id', nid)
        s += self.tag('name', n['label'])
        for p in g.predecessors(nid):
            for _,ea in g[p][nid].items():
                pred = ea['pred']
                if p in g and 'label' in g.node[p]:
                    p = '{} ! {}'.format(p, g.node[p]['label'])
                if pred == 'subClassOf':
                    s += self.tag('is_a', p)
                else:
                    s += self.tag('relationship', pred, p)
        s += "\n"
        return s

    def render_xrefs(self, nid, g, **args):
        n = g.node[nid]
        s = "[Term]\n";
        s += self.tag('id ! TODO', nid)
        s += self.tag('name', n['label'])
        for p in g.predecessors(nid):
            for _,ea in g[p][nid].items():
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
    
class OboJsonGraphRenderer(GraphRenderer):
    """
    Render as obographs json
    """
    def __init__(self, **args):
        super().__init__(**args)
        
    def to_json(self, g, **args):
        obj = {}
        node_objs = []
        for n in g.nodes():
            node_objs.append(self.node_to_json(n, g, **args))
        obj['nodes'] = node_objs
        edge_objs = []
        for e in g.edges_iter(data=True):
            edge_objs.append(self.edge_to_json(e, g, **args))
        obj['edges'] = edge_objs
        return {'graphs' : [obj]}

    def render(self, g, **args):
        obj = self.to_json(g, **args)
        return json.dumps(obj)
    
    def node_to_json(self, nid, g, **args):
        n = g.node[nid]
        return {'id' : nid,
                'lbl' : n.get('label')}
    
    def edge_to_json(self, e, g, **args):
        (obj,sub,meta) = e
        return {'sub' : sub,
                'obj' : obj,
                'pred' : meta['pred']}

    def tag(self, t, *vs):
        v = " ".join(vs)
        return t + ': ' + v + "\n"
    
