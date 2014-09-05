import unicodedata
import json
import re

DEFAULT_LOCALE = 'en-US'
IMAGE_CDN_PATTERN = r'(!\[.*?\]\()\$IMAGE_ROOT(.*?(?:\s?\".*?\")?\))'


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and underscores) and converts spaces to
    hyphens. Also strips leading and trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def convert_to_cdn_path(cdn_path, body):
    return re.sub(IMAGE_CDN_PATTERN, '\\1{}\\2'.format(cdn_path), body)


def to_zendesk_locale(locale):
    return locale.lower()


def to_iso_locale(locale):
    if '-' in locale:
        first, second = locale.split('-')
        return first + '-' + second.upper()
    else:
        return locale
