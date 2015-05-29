import json
from pathlib import Path
from collections import namedtuple

from .utils import slugify
from .model import Handler, Category

DEFAULT_ROOT_DIR = '.'

Storage = namedtuple('Storage', ['save', 'load'])


def is_category(item):
    return 'section_id' not in item and 'category_id' not in item


def is_section(item):
    return 'category_id' in item


def is_article(item):
    return 'section_id' in item


def resolve_path(category='', section=''):
    return Path(category['name'])


def FileStorage():
    def save(path, data):
        with path.open('w') as fp:
            return fp.write(data)

    def load(path):
        with path.open() as fp:
            return fp.read()

    return Storage(
        lambda path, data, **kwargs: save(path, data),
        lambda path, **kwargs: load(path)
    )


def JsonStorage(storage):
    return Storage(
        lambda data, **kwargs: storage.save(data=json.dumps(data), **kwargs),
        lambda **kwargs: json.loads(storage.load(**kwargs))
    )


def GroupContentStorage(storage):
    return Storage(
        lambda item, **kwargs: storage.save(**kwargs),
        lambda path, **kwargs: storage.load(path=path.joinpath('__group__.json'), **kwargs)
    )


def GroupMetaStorage(storage):
    return Storage(
        lambda item, **kwargs: storage.save(**kwargs),
        lambda path, **kwargs: storage.load(path=path.joinpath('.group.meta'), **kwargs)
    )


def GroupStorage(content_storage, meta_storage):
    def load(path, **kwargs):
        for dir_item in path.iterdir():
            if dir_item.is_dir():
                content = content_storage.load(dir_item, **kwargs)
                meta = meta_storage.load(dir_item, **kwargs)
                yield dir_item, content, meta

    return Storage(
        lambda item, **kwargs: storage.save(**kwargs),
        lambda path, **kwargs: load(path, **kwargs)
    )


def CategoryStorage(storage, root_path):
    def load(path, **kwargs):
        for category_path, content, meta in storage.load(path, **kwargs):
            yield Category(category_path, content, meta)

    return Storage(
        lambda **kwargs: storage.save(**kwargs),
        lambda **kwargs: load(root_path, **kwargs)
    )


def SectionStorage(storage):
    def load(path, **kwargs):
        for section_path, content, meta in storage.load(path, **kwargs):
            yield Section(section_path, content, meta, category)

    return Storage(
        lambda **kwargs: storage.save(**kwargs),
        lambda category, **kwargs: storage.load(path=category.path, **kwargs)
    )


def ArticleStorage(storage):
    return Storage(
        lambda **kwargs: storage.save(**kwargs),
        lambda category, section, **kwargs: storage.load(**kwargs)
    )


def storage(config=None, base_storage=FileStorage(), root_path=None):
    config = config or {}
    if root_path is None:
        root_dir = config.get('root_dir', DEFAULT_ROOT_DIR)
        root_path = Path(root_dir)

    json_storage = JsonStorage(base_storage)
    group_content_storage = GroupContentStorage(json_storage)
    group_meta_storage = GroupMetaStorage(json_storage)
    group_storage = GroupStorage(group_content_storage, group_meta_storage)
    category_storage = CategoryStorage(group_storage, root_path)
    section_storage = SectionStorage(group_storage)
    article_storage = ArticleStorage(json_storage)

    return Handler(
        category_storage,
        section_storage,
        article_storage
    )


def items(storage):
    categories = storage.categories.load()
    for category in categories:
        yield category
        sections = storage.sections.load(category)
        for section in sections:
            yield section
            articles = storage.articles.load(category, section)
            for article in articles:
                yield article


def save_item(item):
    pass
