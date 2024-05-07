import click
import os

    
def retracted_pubs_set(abs_docs_path)->set[str]:
    retracted_path = os.path.join(abs_docs_path, "europe-pmc-retracted.txt")
    try:
        retracted_pubs = set()   
        with open(retracted_path, "r") as f:
            for line in f:
                li=line.strip()
                if not li.startswith("!"):
                    if "," in li:
                        li = li.partition(',')[0]
                    retracted_pubs.add(li)
        return retracted_pubs                
    except Exception as e:
         raise click.ClickException("Could not find or read {}: {}".format(retracted_path, str(e)))                        