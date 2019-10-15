import click
import yaml
import os
import glob

from dataclasses import dataclass

import yamldown

from typing import Dict, Set

"""
This module is for interacting with the different types of metadata that live
in the geneontology/go-site/metadata directory
"""

###############################################

class BiDiMultiMap(dict):

    def __init__(self, *args):
        super(BiDiMultiMap, self).__init__(*args)
        self.__reverse = dict()

    def __setitem__(self, key, val):

        # Turn everything into a set
        inval = None
        if isinstance(val, set):
            inval = val
        elif isinstance(val, iter):
            inval = set(val)
        elif val == None:
            inval = set()
        else:
            inval = set([val])

        olds = self.get(key, [])
        super(BiDiMultiMap, self).__setitem__(key, inval)
        # Remove old value mappings from the key
        for old in olds:
            if old in self.__reverse:
                del self.__reverse[old]

        # Add the items
        for v in inval:
            self.__reverse[v] = key

    def __delitem__(self, key):
        vs = self[key]
        super(BiDiMultiMap, self).__delitem__(key)
        for v in vs:
            del self.__reverse[v]


    def reverse(self, element):
        """
        Returns the key that has element in the set for the mapping of `key`, or
        None, of there is no such element.

        Example:
        Given "FB" --> set("fb", "FlyBase")

        reverse("fb") --> "FB"
        reverse("FlyBase") --> "FB"
        reverse("Foo") --> None
        """
        return self.__reverse.get(element, None)

# d = BiDiMultiMap()
#
# d["FB"] = set(["fb", "FlyBase"])
# d.reverse("fb") # returns "FB"
# d.reverse("FlyBase") # returns "FB"
# d.reverse("mgi:mgi") # returns None

###############################################
# 
# @dataclass
# class YamldownMetadata:
#     id: str
#     layout: str
#     _meta: dict
#     _text: str


def yamldown_lookup(yamldown_dir):
    d = {
        metayaml_id(meta_path): get_yamldown_metadata(yamldown_dir, metayaml_id(meta_path))
        for meta_path in glob.glob("{}/*.md".format(os.path.join(yamldown_dir))) if metayaml_id(meta_path) not in ["ABOUT", "README", "SOP", "README-editors"]
    }
    
    return d

def dataset_metadata_file(metadata, group, empty_ok=False) -> Dict:
    metadata_yaml = os.path.join(metadata, "datasets", "{}.yaml".format(group))
    try:
        with open(metadata_yaml, "r") as group_data:
            click.echo("Found {group} metadata at {path}".format(group=group, path=metadata_yaml))
            return yaml.load(group_data, Loader=yaml.FullLoader)
    except Exception as e:
        if not empty_ok:
            raise click.ClickException("Could not find or read {}: {}".format(metadata_yaml, str(e)))
        else:
            return None

def gorule_title(metadata, rule_id) -> str:
    return gorule_metadata(metadata, rule_id)["title"]

def gorule_metadata(metadata, rule_id) -> dict:
    gorule_yamldown = os.path.join(metadata, "rules")
    return get_yamldown_metadata(gorule_yamldown, rule_id)
        
def parse_goref_metadata(metadata, goref_id) -> dict:
    goref_yamldown = os.path.join(metadata, "gorefs")
    return get_yamldown_metadata(goref_yamldown, goref_id)

def get_yamldown_metadata(yamldown_dir, meta_id) -> dict:
    yamldown_md_path = os.path.join(yamldown_dir, "{}.md".format(meta_id))
    try:
        with open(yamldown_md_path, "r") as gorule_data:
            return yamldown.load(gorule_data)[0]
    except Exception as e:
        raise click.ClickException("Could not find or read {}: {}".format(yamldown_md_path))

def metayaml_id(rule_path) -> str:
    return os.path.splitext(os.path.basename(rule_path))[0]

def source_path(dataset_metadata, target_dir, group):
    extension = dataset_metadata["type"]
    if dataset_metadata["compression"]:
        extension = "{ext}.gz".format(ext=extension)

    path = os.path.join(target_dir, "groups", group, "{name}-src.{ext}".format(name=dataset_metadata["dataset"], ext=extension))
    return path
    
def database_entities(metadata):
    dbxrefs_path = os.path.join(os.path.abspath(metadata), "db-xrefs.yaml")
    try:
        with open(dbxrefs_path, "r") as db_xrefs_file:
            click.echo("Found db-xrefs at {path}".format(path=dbxrefs_path))
            dbxrefs = yaml.load(db_xrefs_file, Loader=yaml.FullLoader)
    except Exception as e:
        raise click.ClickException("Could not find or read {}: {}".format(dbxrefs_path, str(e)))

    d = BiDiMultiMap()
    for entity in dbxrefs:
        d[entity["database"]] = set(entity.get("synonyms", []))

    return d

def groups(metadata) -> Set[str]:
    groups_path = os.path.join(os.path.abspath(metadata), "groups.yaml")
    try:
        with open(groups_path, "r") as groups_file:
            click.echo("Found groups at {path}".format(path=groups_path))
            groups_list = yaml.load(groups_file, Loader=yaml.FullLoader)
    except Exception as e:
        raise click.ClickException("Could not find or read {}: {}".format(groups_path, str(e)))

    return set([group["shorthand"] for group in groups_list])
    
