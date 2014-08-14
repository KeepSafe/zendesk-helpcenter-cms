import os
import html2text

import utils
import services


class AbstractItem(object):
    TRANSLATE_KEY = 'webtranslateit_ids'
    ZENDESK_KEY = 'id'

    def __init__(self, path):
        os.makedirs(path, exist_ok=True)
        self.meta_repo = services.MetaService()
        self.content_repo = services.ContentService()
        self.path = path

    @property
    def meta(self):
        return self.meta_repo.read(self.meta_filename)

    @meta.setter
    def meta(self, value):
        self.meta_repo.save(self.meta_filename, value)

    @property
    def content(self):
        return utils.from_json(self.content_repo.read(self.content_filename))

    @content.setter
    def content(self, value):
        self.content_repo.save(self.content_filename, utils.to_json(value))

    @property
    def content_filename(self):
        return os.path.join(self.path, self._content_filename)

    @property
    def meta_filename(self):
        return os.path.join(self.path, self._meta_filename)

    @property
    def zendesk_id(self):
        data = self.meta_repo.read(self.meta_filename)
        if data:
            return data.get(AbstractItem.ZENDESK_KEY)
        else:
            return None

    @property
    def translate_ids(self):
        data = self.meta_repo.read(self.meta_filename)
        if data:
            return data.get(AbstractItem.TRANSLATE_KEY)
        else:
            return []

    def fixme(self, content):
        os.makedirs(self.path, exist_ok=True)
        if not os.path.exists(self.content_filename):
            self.content = content

    def _translations(self, filepath):
        result = {}
        master_name, master_ext = os.path.splitext(os.path.basename(filepath))
        files = [file for file in os.listdir(self.path) if file.startswith(master_name) and file.endswith(master_ext)]
        for file in files:
            if file == os.path.basename(filepath):
                result[utils.DEFAULT_LOCALE] = os.path.join(self.path, file)
            else:
                name, ext = os.path.splitext(file)
                locale = name.split('.')[-1]
                result[locale] = os.path.join(self.path, file)
        return result


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
        article_names = filter(lambda a: a.endswith('.md'), filepaths)
        article_names_bits = map(lambda a: a.split('.'), article_names)
        article_names_bits = filter(lambda a: len(a) == 2, article_names_bits)
        article_names = map(lambda a: a[0], article_names_bits)
        articles = [Article(article_dir, article_name) for article_name in article_names]
        return articles

    def _subgroups(self):
        filepaths = [filepath for filepath in os.listdir(
            self.path) if os.path.isdir(os.path.join(self.path, filepath))]
        return [Group(os.path.join(self.path, filepath), self) for filepath in filepaths]

    @property
    def children(self):
        if self.parent:
            return self._articles()
        else:
            return self._subgroups()

    @property
    def translations(self):
        return self._translations(self.content_filename)

    def fixme(self):
        super().fixme({'name': os.path.basename(self.path), 'description': ''})

    def remove(self):
        for child in self.children:
            child.remove()
        for locale, filepath in self.translations.items():
            self.content_repo.remove(filepath)
        self.meta_repo.remove(self.meta_filename)
        self.content_repo.remove_group(self.path)

    def move_to(self, group):
        self.content_repo.move(self.path, group.path)
        self.path = os.path.join(group.path, os.path.basename(self.path))

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

    @property
    def body_filename(self):
        return os.path.join(self.path, '{}.md'.format(self.name))

    @property
    def body(self):
        return self.content_repo.read(self.body_filename)

    @body.setter
    def body(self, value):
        self.content_repo.save(self.body_filename, value)

    @property
    def attachments_path(self):
        return os.path.join(self.path, self.name + '_attachments')

    @property
    def translations(self):
        body_translations = self._translations(self.body_filename)
        content_translations = self._translations(self.content_filename)
        return {locale: [content, body_translations[locale]] for locale, content in content_translations.items()}

    def remove(self):
        for locale, (content_filepath, body_filepath) in self.translations.items():
            self.content_repo.remove(content_filepath)
            self.content_repo.remove(body_filepath)
        self.meta_repo.remove(self.meta_filename)

    def move_to(self, group):
        for locale, (content_filepath, body_filepath) in self.translations.items():
            self.content_repo.move(content_filepath, group.path)
            self.content_repo.move(body_filepath, group.path)
        self.meta_repo.move(self.meta_filename, group.path)
        self.path = group.path

    def fixme(self):
        super().fixme({'name': self.name})

    @staticmethod
    def from_zendesk(section_path, zendesk_article):
        name = zendesk_article['name']
        locale = zendesk_article['locale']
        article_path = os.path.join(section_path, locale)
        article = Article(article_path, utils.slugify(name))
        article.meta = zendesk_article
        article.content = {'name': name}
        article.body = html2text.html2text(zendesk_article['body'])
        return article
