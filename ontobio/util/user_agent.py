from ontobio import __version__ as ontobio_version


def get_user_agent(name="ontobio", version=ontobio_version, modules=None, caller_name=None):
    """
    Create a User-Agent string
    """

    user_agent_array = ["{}/{}".format(name, version)]
    if modules:
        module_info_array = []
        for m in modules:
            mod_name = m.__name__
            mod_version = None
            if hasattr(m, 'get_version'):
                mod_version = m.get_version()
            else:
                mod_version = m.__version__
            module_info_array.append("{}/{}".format(mod_name, mod_version))

        if caller_name:
            module_info_array.append(caller_name)

        user_agent_array.append("({})".format('; '.join(module_info_array)))
    else:
        if caller_name:
            user_agent_array.append("({})".format(caller_name))

    return ' '.join(user_agent_array)
