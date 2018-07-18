from ontobio import __version__ as ontobio_version

def get_user_agent(name="ontobio", version=ontobio_version, caller_name=""):
    """
    Create a user agent string
    """

    user_agent = "{} {} [{}] (ontobio/{})".format(name, version, caller_name, ontobio_version)
    return user_agent
