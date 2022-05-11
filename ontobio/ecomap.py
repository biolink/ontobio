import requests
from contextlib import closing
import logging

from ontobio.util.user_agent import get_user_agent

logger = logging.getLogger(__name__)


def get_ecomap_str(url):
    logger.info("Fetching ecomap from {}".format(url))
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
    PURL_DERIVED = 'http://purl.obolibrary.org/obo/eco/gaf-eco-mapping-derived.txt'

    def __init__(self):
        self._mappings = None
        self._derived_mappings = None
    
    def mappings(self):
        if self._mappings is None:
            s = get_ecomap_str(self.PURL)
            self._mappings = self.parse_ecomap_str(s)
        return self._mappings

    def derived_mappings(self):
        if self._derived_mappings is None:
            s = get_ecomap_str(self.PURL_DERIVED)
            self._derived_mappings = self.parse_derived_ecomap_str(s)
        return self._derived_mappings

    def parse_ecomap_str(self, str):
        lines = str.split("\n")
        tups = []
        for line in lines:
            if line.startswith('#'):
                continue
            if line == "":
                continue
            logger.debug("LINE={}".format(line))
            [code, ref, cls] = line.split("\t")
            if ref == 'Default':
                ref = None
            tups.append( (code, ref, cls) )
        return tups

    def parse_derived_ecomap_str(self, str):
        lines = str.split("\n")
        tups = []
        for line in lines:
            if line.startswith('#'):
                continue
            if line == "":
                continue
            logger.debug("LINE={}".format(line))
            [cls, code, default] = line.split("\t")
            if default == 'Default':
                default = None
            tups.append((code, default, cls))
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
        for (this_code, this_ref, cls) in self.mappings():
            if str(this_code) == str(code):
                if this_ref == reference:
                    return cls
                if this_ref is None:
                    mcls = cls
                    
        return mcls
                
    def ecoclass_to_coderef(self, cls, derived=False):
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
        if derived:
            mappings = self.derived_mappings()
        else:
            mappings = self.mappings()
        for (code, ref, this_cls) in mappings:
            if cls == this_cls:
                return code, ref
        return None, None
