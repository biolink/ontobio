import requests
from contextlib import closing
from cachier import cachier
import datetime
import logging

from ontobio.util.user_agent import get_user_agent

SHELF_LIFE = datetime.timedelta(days=1)

@cachier(stale_after=SHELF_LIFE)
def get_ecomap_str(url):
    logging.info("Fetching ecomap from {}".format(url))
    with closing(requests.get(url, stream=False, headers={'User-Agent': get_user_agent(modules=[requests], caller_name=__name__)})) as resp:
        # TODO: redirects
        if resp.status_code == 200:
            return resp.text

#E.g.
# IEA	Default	ECO:0000501
# IEA	GO_REF:0000002	ECO:0000256
# IEA	GO_REF:0000003	ECO:0000501

class EcoMap():
    """
    Provides mapping between GO Evidence codes (IDA, IEA, ISS, etc) and ECO classes.

    The mapping is actually between a (code, ref) pair and an eco class
    """

    PURL = 'http://purl.obolibrary.org/obo/eco/gaf-eco-mapping.txt'

    def __init__(self):
        self._mappings = None
    
    def mappings(self):
        if self._mappings is None:
            s = get_ecomap_str(self.PURL)
            self._mappings = self.parse_ecomap_str(s)
        return self._mappings

    def parse_ecomap_str(self, str):
        lines = str.split("\n")
        tups = []
        for line in lines:
            if line.startswith('#'):
                continue
            if line == "":
                continue
            logging.info("LINE={}".format(line))
            [code, ref, cls] = line.split("\t")
            if ref == 'Default':
                ref = None
            tups.append( (code, ref, cls) )
        return tups
                
    def coderef_to_ecoclass(self, code, reference=None):
        """
        Map a GAF code to an ECO class

        Arguments
        ---------
        code : str
            GAF evidence code, e.g. ISS, IDA
        reference: str
            CURIE for a reference for the evidence instance. E.g. GO_REF:0000001.
            Optional - If provided can give a mapping to a more specific ECO class

        Return
        ------
        str
            ECO class CURIE/ID
        """
        mcls = None
        for (this_code,this_ref,cls) in self.mappings():
            if str(this_code) == str(code):
                if this_ref  == reference:
                    return cls
                if this_ref is None:
                    mcls = cls
                    
        return mcls
                
    def ecoclass_to_coderef(self, cls):
        """
        Map an ECO class to a GAF code

        This is the reciprocal to :ref:`coderef_to_ecoclass`

        Arguments
        ---------
        cls : str
            GAF evidence code, e.g. ISS, IDA
        reference: str
            ECO class CURIE/ID

        Return
        ------
        (str, str)
            code, reference tuple
        """
        code = ''
        ref = None
        for (code,ref,this_cls) in self.mappings():
            if cls == this_cls:
                return code, ref
        return None, None
