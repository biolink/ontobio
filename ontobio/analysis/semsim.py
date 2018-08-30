from ontobio.assocmodel import AssociationSet

def jaccard_similarity(aset:AssociationSet, s1:str, s2:str) -> float:
    """
    Calculate jaccard index of inferred associations of two subjects

    |ancs(s1) /\ ancs(s2)|
    ---
    |ancs(s1) \/ ancs(s2)|

    """
    a1 = aset.inferred_types(s1)
    a2 = aset.inferred_types(s2)
    num_union = len(a1.union(a2))
    if num_union == 0:
        return 0.0
    return len(a1.intersection(a2)) / num_union
