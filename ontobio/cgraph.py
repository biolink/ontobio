
class CompactGraph():

    def __init__(self, nodes=None, edges=None):
        if nodes is None:
            nodes = []
        if edges is None:
            edges = []

        id2index = {}
        label_arr = []
        id_arr = []

        e_by_p = {}
        o_by_ps = {}
        
        i = 0

            
        # TODO: order nodes
        # TODO: include undeclared
        for n in nodes:
            id = n.id
            id2index[id] = i
            i = i+1
            id_arr.append(id)
            label_arr.append(n.lbl)
            
        for e in edges:
            ids = [e.sub,e.pred,e.obj]
            for id in ids:
                if id not in id2index:
                    id2index[id] = i
                    i = i+1
                    id_arr.append(id)
                    label_arr.append(id)
            
        for e in edges:
            (s,p,o) = (e.sub,e.pred,e.obj)
            (si,pi,oi) = (id2index[s],id2index[p],id2index[o])
            if pi not in e_by_p:
                e_by_p[pi] = []
            e_by_p[pi].append((si,oi))
            if pi not in o_by_ps:
                o_by_ps[pi] = {}
            if si not in o_by_ps[pi]:
                o_by_ps[pi][si] = []
            o_by_ps[pi][si].append(oi)

        self.id2index = id2index
        self.id_arr = id_arr
        self.label_arr = label_arr
        self.e_by_p = e_by_p
        self.o_by_ps = o_by_ps

    def parse(self):
        print("TODO")
        
    def serialize(self):
        for id in self.id_arr:
            ix = self.id2index[id]
            lbl = self.label_arr[ix]
            print("{}\t{}".format(id,lbl))
        print("#EDGES")
        for (pi,o_by_s) in self.o_by_ps.items():
            print("#P:{}".format(pi))
            for (s,olist) in o_by_s.items():
                olist_str = "\t".join([str(x) for x in olist])
                print("{}\t{}".format(str(s),olist_str))
        #for (p,tuples) in self.e_by_p.items():
        #    print("#P:{}",p)
        #    for (s,o) in tuples:
        #        print("{}\t{}".format(s,o))
                  
            
            

