import os
import utils
import markdown

DEFAULT_LOCALE = 'en-US'


class Base(object):
    _meta_exp = '.meta'
    _content_exp = '.json'
    _translate_id_key = 'webtranslateit_ids'
    _zendesk_id_key = 'id'

    def __init__(self, name, filename):
        super().__init__()
        self.name = name
        self.filename = filename
        self.translations = []
        self._meta = {}

    @property
    def meta(self):
        return self._meta

    @meta.setter
    def meta(self, value):
        self._meta = value or {}

    @property
    def zendesk_id(self):
        return self._meta.get(self._zendesk_id_key)

    @property
    def translate_ids(self):
        return self._meta.get(self._translate_id_key, [])

    @property
    def meta_filepath(self):
        return os.path.join(self.path, self.meta_filename + self._meta_exp)

    @property
    def content_filepath(self):
        return os.path.join(self.path, self.content_filename + self._content_exp)


# TODO use for default locale
class GroupTranslation(object):

    def __init__(self, locale, name, description):
        self.locale = locale or DEFAULT_LOCALE
        self.name = name
        self.description = description

    def to_dict(self, image_cdn=None):
        return {
            'title': self.name,
            'body': self.description,
            'locale': utils.to_zendesk_locale(self.locale)
        }


class Group(Base):
    meta_filename = '.group'
    content_filename = '__group__'

    def __init__(self, name, description, filename):
        super().__init__(name, filename)
        self.description = description

    def to_content(self):
        return {
            'name': self.name,
            'description': self.description
        }

    def to_dict(self, image_cdn=None):
        return {
            'name': self.name,
            'description': self.description,
            'locale': utils.to_zendesk_locale(DEFAULT_LOCALE)
        }

    def content_translation_filepath(self, locale):
        if locale:
            locale = '.' + locale
        return os.path.join(self.path, self.content_filename + locale + self._content_exp)


class Category(Group):
    def __init__(self, name, description, filename):
        super().__init__(name, description, filename)
        self.sections = []

    @property
    def path(self):
        return self.filename

    @staticmethod
    def from_dict(meta, content, filename):
        name = content['name']
        description = content.get('description', '')
        category = Category(name, description, filename)
        category.meta = meta
        return category

    @classmethod
    def filepaths_from_path(cls, path):
        meta_path = os.path.join(path, cls.meta_filename + cls._meta_exp)
        content_path = os.path.join(path, cls.content_filename + cls._content_exp)
        return meta_path, content_path

    @property
    def new_item_url(self):
        return 'categories.json'


class Section(Group):

    def __init__(self, category, name, description, filename):
        super().__init__(name, description, filename)
        self.articles = []
        self.category = category

    @property
    def path(self):
        return os.path.join(self.category.path, self.filename)

    @classmethod
    def filepaths_from_path(cls, category, path):
        meta_path = os.path.join(category.path, path, cls.meta_filename + cls._meta_exp)
        content_path = os.path.join(category.path, path, cls.content_filename + cls._content_exp)
        return meta_path, content_path

    @staticmethod
    def from_dict(category, meta, content, filename):
        name = content['name']
        description = content.get('description', '')
        section = Section(category, name, description, filename)
        section.meta = meta
        return section

    @property
    def new_item_url(self):
        return 'categories/{}/sections.json'.format(self.category.zendesk_id)


# TODO use for default locale
class ArticleTranslation(object):
    def __init__(self, locale, name, body):
        self.locale = locale
        self.name = name
        self.body = body

    def to_dict(self, image_cdn=None):
        if image_cdn:
            body = utils.convert_to_cdn_path(image_cdn, self.body)
        body = markdown.markdown(body)

        return {
            'title': self.name,
            'body': body,
            'locale': utils.to_zendesk_locale(self.locale)
        }


class Article(Base):
    _body_exp = '.mkdown'
    _meta_pattern = '.article_{}'

    def __init__(self, section, name, body, filename):
        super().__init__(name, filename)
        self.body = body
        self.section = section

    @property
    def meta_filename(self):
        return self._meta_pattern.format(self.content_filename)

    @property
    def content_filename(self):
        return self.filename

    @property
    def body_filepath(self):
        return os.path.join(self.path, self.content_filename + self._body_exp)

    @property
    def path(self):
        return self.path_from_section(self.section)

    def to_dict(self, image_cdn=None):
        if image_cdn:
            body = utils.convert_to_cdn_path(image_cdn, self.body)
        body = markdown.markdown(body)
        return {
            'title': self.name,
            'body': body,
            'locale': utils.to_zendesk_locale(DEFAULT_LOCALE)
        }

    def to_content(self):
        return {
            'name': self.name
        }

    def content_translation_filepath(self, locale):
        return os.path.join(os.path.dirname(self.path), locale, self.content_filename + self._content_exp)

    def body_translation_filepath(self, locale):
        return os.path.join(os.path.dirname(self.path), locale, self.content_filename + self._body_exp)

    @staticmethod
    def path_from_section(section):
        return os.path.join(section.path, DEFAULT_LOCALE)

    @classmethod
    def filepaths_from_path(cls, section, name):
        path = cls.path_from_section(section)
        meta_path = os.path.join(path, cls._meta_pattern.format(name) + cls._meta_exp)
        content_path = os.path.join(path, name + cls._content_exp)
        body_path = os.path.join(path, name + cls._body_exp)
        return meta_path, content_path, body_path

    @staticmethod
    def from_dict(section, meta, content, body, filename):
        article = Article(section, content['name'], body, filename)
        article.meta = meta
        return article

    @property
    def new_item_url(self):
        return 'sections/{}/articles.json'.format(self.section.zendesk_id)
