import gzip
import click
import os

from functools import wraps

def gzips(file_function):

    @wraps(file_function)
    def wrapper(*args, **kwargs):
        output_file = file_function(*args, **kwargs)
        if isinstance(output_file, list):
            for o in output_file:
                zipup(o)
        else:
            zipup(output_file)

        return output_file

    return wrapper

def zipup(file_path):
    click.echo("Zipping {}".format(file_path))
    path, filename = os.path.split(file_path)
    zipname = "{}.gz".format(filename)
    target = os.path.join(path, zipname)

    with open(file_path, "rb") as p:
        with gzip.open(target, "wb") as tf:
            tf.write(p.read())
            
def unzip(path, target):
    click.echo("Unzipping {}".format(path))
    def chunk_gen():
        with gzip.open(path, "rb") as p:
            while True:
                chunk = p.read(size=512 * 1024)
                if not chunk:
                    break
                yield chunk

    with open(target, "wb") as tf:
        with click.progressbar(iterable=chunk_gen()) as chunks:
            for chunk in chunks:
                tf.write(chunk)

def find(l, finder):
    filtered = [n for n in l if finder(n)]
    if len(filtered) == 0:
        return None
    else:
        return filtered[0]
