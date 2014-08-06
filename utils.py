import unicodedata
import json
import re

DEFAULT_LOCALE = 'en-us'


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and underscores) and converts spaces to
    hyphens. Also strips leading and trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def to_json(data):
    return json.dumps(data, indent=4, sort_keys=True)


def from_json(data):
    return json.loads(data)


class Logger(object):

    """
    Logs messages to stdout. Has 2 levels, info and debug, with debug only being used if verbose is True.
    """

    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose

    def debug(self, message, *args):
        if self.verbose:
            print(message.format(*args))

    def info(self, message, *args):
        print(message.format(*args))
