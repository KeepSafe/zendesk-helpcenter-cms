import os
import html2text
import logging

import utils
import services

MARKDOWN_EXTENSION = '.mkdown'


class AbstractItem(object):
    TRANSLATE_KEY = 'webtranslateit_ids'
    ZENDESK_KEY = 'id'

    def __init__(self, path):
        os.makedirs(path, exist_ok=True)
        self.path = path

    @property
    def meta(self):
        return services.filesystem.read(self.meta_filename)

    @meta.setter
    def meta(self, value):
        services.filesystem.save(self.meta_filename, value)

    @property
    def content(self):
        return services.filesystem.read(self.content_filename)

    @content.setter
    def content(self, value):
        services.filesystem.save(self.content_filename, value)

    @property
    def content_filename(self):
        return os.path.join(self.path, self._content_filename)

    @property
    def meta_filename(self):
        return os.path.join(self.path, self._meta_filename)

    @property
    def zendesk_id(self):
        data = self.meta
        if data:
            return data.get(AbstractItem.ZENDESK_KEY)
        else:
            return None

    @property
    def translate_ids(self):
        data = self.meta
        if data:
            return data.get(AbstractItem.TRANSLATE_KEY)
        else:
            return []

    @property
    def comments_disabled(self):
        data = self.meta
        if data:
            return data.get('comments_disabled', False)
        else:
            return False

    def fixme(self, content):
        if not os.path.exists(self.content_filename):
            for key, value in content.items():
                new_value = input('Please provide a {} for this item (default: {})'.format(key, value))
                new_value = new_value or value
                content[key] = new_value
            self.content = content


class Group(AbstractItem):

    def __init__(self, path, parent=None):
        super().__init__(path)
        self.parent = parent
        self._content_filename = '__group__.json'
        self._meta_filename = '.group.meta'

    def _articles(self):
        locale = utils.DEFAULT_LOCALE
        article_dir = os.path.join(self.path, locale)
        filepaths = [filepath for filepath in os.listdir(article_dir)
                     if os.path.isfile(os.path.join(article_dir, filepath))]
        article_names = filter(lambda a: a.endswith(MARKDOWN_EXTENSION), filepaths)
        article_names_bits = map(lambda a: a.split('.'), article_names)
        article_names_bits = filter(lambda a: len(a) == 2, article_names_bits)
        article_names = map(lambda a: a[0], article_names_bits)
        articles = [Article(article_dir, article_name) for article_name in article_names]
        return articles

    def _subgroups(self):
        filepaths = [filepath for filepath in os.listdir(
            self.path) if os.path.isdir(os.path.join(self.path, filepath))]
        return [Group(os.path.join(self.path, filepath), self) for filepath in filepaths]

    def _is_section(self):
        return self.parent is not None

    @property
    def children(self):
        # categories have no parents, sections have categories as parents
        if self._is_section():
            return self._articles()
        else:
            return self._subgroups()

    @property
    def translations(self):
        result = {}
        master_name, master_ext = os.path.splitext(os.path.basename(self.content_filename))
        files = [file for file in os.listdir(self.path) if file.startswith(master_name) and file.endswith(master_ext)]
        for file in files:
            if file == os.path.basename(self.content_filename):
                result[utils.DEFAULT_LOCALE] = os.path.join(self.path, file)
            else:
                name, ext = os.path.splitext(file)
                locale = name.split('.')[-1]
                result[locale] = os.path.join(self.path, file)
        return result

    def fixme(self):
        self._create_missing_locales()
        self._slugify_name()
        super().fixme({'name': os.path.basename(self.path), 'description': ''})

    def remove(self):
        for child in self.children:
            child.remove()
        for locale, filepath in self.translations.items():
            services.filesystem.remove(filepath)
        services.filesystem.remove(self.meta_filename)
        services.filesystem.remove_group(self.path)

    def move_to(self, group):
        services.filesystem.move(self.path, group.path)
        self.path = os.path.join(group.path, os.path.basename(self.path))

    def _create_missing_locales(self):
        if not self._is_section():
            return
        logging.debug('creating missing locales directories in %s', self.path)
        locales = [utils.to_iso_locale(locale) for locale in services.zendesk.available_locales()]
        for locale in locales:
            locale_path = os.path.join(self.path, locale)
            if not os.path.exists(locale_path):
                logging.debug('creating directory for locale %s', locale)
                os.makedirs(locale_path, exist_ok=True)

    def _slugify_name(self):
        name = os.path.basename(self.path)
        slugify_name = utils.slugify(name)
        if name != slugify_name:
            slugify_path = os.path.join(os.path.dirname(self.path), slugify_name)
            services.filesystem.move(self.path, slugify_path)
            self.path = slugify_path
            super().fixme({'name': name, 'description': ''})
            if self.translate_ids:
                translate_id, = self.translate_ids
                services.translate.move(translate_id, self.content_filename)

    @staticmethod
    def from_zendesk(parent_path, zendesk_group, parent=None):
        name = zendesk_group['name']
        path = os.path.join(parent_path, utils.slugify(name))
        group = Group(path, parent)
        group.meta = zendesk_group
        group.content = {'name': name, 'description': zendesk_group['description']}
        return group

    @staticmethod
    def from_path(root, path):
        if root.strip('/') == os.path.dirname(path).strip('/'):
            return Group(path), None
        else:
            category = Group(os.path.dirname(path))
            return category, Group(path, category)


class Article(AbstractItem):

    def __init__(self, path, name):
        super().__init__(path)
        self.name = name
        self._content_filename = '{}.json'.format(self.name)
        self._meta_filename = '.article_{}.meta'.format(self.name)
        self._body_filename = self.name + MARKDOWN_EXTENSION

    @property
    def body_filename(self):
        return os.path.join(self.path, self._body_filename)

    @property
    def body(self):
        return services.filesystem.read(self.body_filename, file_format='text')

    @body.setter
    def body(self, value):
        services.filesystem.save(self.body_filename, value, file_format='text')

    @property
    def attachments_path(self):
        return os.path.join(self.path, self.name + '_attachments')

    @property
    def translations(self):
        body_translations = self._translations(self._body_filename)
        content_translations = self._translations(self._content_filename)
        return {locale: [content, body_translations[locale]] for locale, content in content_translations.items()}

    def _translations(self, filename):
        section_path = os.path.dirname(self.path)
        locales = [locale for locale in os.listdir(section_path) if os.path.isdir(os.path.join(section_path, locale))]
        return {locale: os.path.join(section_path, locale, filename) for locale in locales}

    def remove(self):
        for locale, (content_filepath, body_filepath) in self.translations.items():
            services.filesystem.remove(content_filepath)
            services.filesystem.remove(body_filepath)
        services.filesystem.remove(self.meta_filename)

    def move_to(self, group):
        for locale, (content_filepath, body_filepath) in self.translations.items():
            services.filesystem.move(content_filepath, group.path)
            services.filesystem.move(body_filepath, group.path)
        services.filesystem.move(self.meta_filename, group.path)
        self.path = group.path

    def fixme(self):
        super().fixme({'name': self.name})
        self._slugify_name()

    def _slugify_name(self):
        slugify_name = utils.slugify(self.name)
        if slugify_name != self.name:
            body_filepath = self.body_filename
            content_filename = self.content_filename
            translations = self.translations

            self.name = slugify_name
            self._content_filename = '{}.json'.format(self.name)
            self._meta_filename = '.article_{}.meta'.format(self.name)
            self._body_filename = self.name + MARKDOWN_EXTENSION

            slugify_body_filepath = self.body_filename
            slugify_content_filename = self.content_filename
            slugify_translations = self.translations

            services.filesystem.move(body_filepath, slugify_body_filepath)
            services.filesystem.move(content_filename, slugify_content_filename)
            for translation_key in translations:
                content_translation, body_translation = translations[translation_key]
                slugify_content_translation, slugify_body_translation = slugify_translations[translation_key]
                if os.path.exists(body_translation):
                    services.filesystem.move(body_translation, slugify_body_translation)
                if os.path.exists(content_translation):
                    services.filesystem.move(content_translation, slugify_content_translation)

            if self.translate_ids:
                body_translate_id, content_translate_id = self.translate_ids
                services.translate.move(body_translate_id, self.body_filename)
                services.translate.move(content_translate_id, self.content_filename)

    @staticmethod
    def from_zendesk(section_path, zendesk_article):
        name = zendesk_article['name']
        locale = utils.to_iso_locale(zendesk_article['locale'])
        article_path = os.path.join(section_path, locale)
        article = Article(article_path, utils.slugify(name))
        article.meta = zendesk_article
        article.content = {'name': name}
        article.body = html2text.html2text(zendesk_article['body'])
        return article
