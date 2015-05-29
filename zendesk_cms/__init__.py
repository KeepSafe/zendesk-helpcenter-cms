"""
KeepSafe's CMS for dealing with Zendesk Help Center and WebTranslateIt.
"""

from . import zendesk, fs

config = {}

def import_all(config):
    for item in zendesk.items():
        fs.save_item(item)

def export_all(config):
    for item in fs.items():
        zendesk.save_item(item)

def doctor(config):
    for item in fs.items():
        fs.validate_item(item)
        zendesk.sync_item(item)
