"""
    translator
    ~~~~~~~~~~

    Manages zendesk help center translations.

    :copyright: (c) 2014 by KeepSafe.
"""
import argparse
import json
import os
import html2text
import markdown
import requests
import shutil
import configparser
import unicodedata
import re


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


LOG = Logger()
DEFAULT_LOCALE = 'en-us'


class Group(object):

    def __init__(self, path, parent=None):
        os.makedirs(path, exist_ok=True)
        self.meta_repo = MetaRepository()
        self.content_repo = ContentRepository()
        self.path = path
        self.parent = parent

    def _articles(self):
        filepaths = [filepath for filepath in os.listdir(self.path)
                     if os.path.isfile(os.path.join(self.path, filepath))]
        article_names = filter(lambda a: a.endswith('.md'), filepaths)
        article_names_bits = map(lambda a: a.split('.'), article_names)
        article_names_bits = filter(lambda a: len(a) == 2, article_names_bits)
        article_names = map(lambda a: a[0], article_names_bits)
        articles = [Article(self.path, article_name) for article_name in article_names]
        return articles

    def _subgroups(self):
        filepaths = [filepath for filepath in os.listdir(
            self.path) if os.path.isdir(os.path.join(self.path, filepath))]
        return [Group(os.path.join(self.path, filepath), self) for filepath in filepaths]

    @property
    def meta_filename(self):
        return os.path.join(self.path, '.group.meta')

    @property
    def content_filename(self):
        return os.path.join(self.path, '__group__.json')

    @property
    def meta(self):
        return self.meta_repo.read(self.meta_filename)

    @meta.setter
    def meta(self, value):
        self.meta_repo.save(self.meta_filename, value)

    @property
    def content(self):
        return from_json(self.content_repo.read(self.content_filename))

    @content.setter
    def content(self, value):
        self.content_repo.save(self.content_filename, to_json(value))

    @property
    def children(self):
        if self.parent:
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
                result[DEFAULT_LOCALE] = os.path.join(self.path, file)
            else:
                name, ext = os.path.splitext(file)
                locale = name.split('.')[-1]
                result[locale] = os.path.join(self.path, file)
        return result

    @property
    def zendesk_id(self):
        data = self.meta_repo.read(self.meta_filename)
        if data:
            return self.meta_repo.read(self.meta_filename).get('id')
        else:
            return None

    @property
    def translate_ids(self):
        data = self.meta_repo.read(self.meta_filename)
        if data:
            return self.meta_repo.read(self.meta_filename).get('webtranslateit_ids')
        else:
            return []

    def fixme(self):
        os.makedirs(self.path, exist_ok=True)
        if not os.path.exists(self.content_filename):
            self.content = {'name': os.path.basename(self.path), 'description': ''}

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
        name = slugify(zendesk_group['name'])
        path = os.path.join(parent_path, name)
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


class Article(object):

    def __init__(self, path, name):
        self.meta_repo = MetaRepository()
        self.content_repo = ContentRepository()
        self.path = path
        self.name = name

    @property
    def body_filename(self):
        return os.path.join(self.path, '{}.md'.format(self.name))

    @property
    def content_filename(self):
        return os.path.join(self.path, '{}.json'.format(self.name))

    @property
    def meta_filename(self):
        return os.path.join(self.path, '.article_{}.meta'.format(self.name))

    @property
    def meta(self):
        return self.meta_repo.read(self.meta_filename)

    @meta.setter
    def meta(self, value):
        self.meta_repo.save(self.meta_filename, value)

    @property
    def content(self):
        return self.content_repo.read(self.content_filename)

    @content.setter
    def content(self, value):
        self.content_repo.save(self.content_filename, to_json(value))

    @property
    def body(self):
        return self.content_repo.read(self.body_filename)

    @body.setter
    def body(self, value):
        self.content_repo.save(self.body_filename, value)

    @property
    def zendesk_id(self):
        data = self.meta_repo.read(self.meta_filename)
        if data:
            return self.meta_repo.read(self.meta_filename).get('id')
        else:
            return None

    @property
    def attachments_path(self):
        return os.path.join(self.path, self.name + '_attachments')

    @property
    def translate_ids(self):
        data = self.meta_repo.read(self.meta_filename)
        if data:
            return self.meta_repo.read(self.meta_filename).get('webtranslateit_ids')
        else:
            return []

    @property
    def translations(self):
        body_translations = self._translations(self.content_filename)
        content_translations = self._translations(self.body_filename)
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

    def _translations(self, filepath):
        result = {}
        master_name, master_ext = os.path.splitext(os.path.basename(filepath))
        files = [file for file in os.listdir(self.path) if file.startswith(master_name) and file.endswith(master_ext)]
        for file in files:
            if file == os.path.basename(filepath):
                result[DEFAULT_LOCALE] = os.path.join(self.path, file)
            else:
                name, ext = os.path.splitext(file)
                locale = name.split('.')[-1]
                result[locale] = os.path.join(self.path, file)
        return result

    def fixme(self):
        os.makedirs(self.path, exist_ok=True)
        if not os.path.exists(self.content_filename):
            self.content = {'name': self.name}

    @staticmethod
    def from_zendesk(section_path, zendesk_article):
        name = slugify(zendesk_article['name'])
        article = Article(section_path, name)
        article.meta = zendesk_article
        article.content = {'name': zendesk_article['name']}
        article.body = html2text.html2text(zendesk_article['body'])
        return article


class MetaRepository(object):

    """
    Handles all meta content, meaning the content coming from Zendesk. Normally just dumps json from Zendesk to a file
    and reads whatever is needed from there. Also has some utility methods which requite meta info.
    """

    def read(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                return json.load(file)
        return None

    def save(self, filepath, data):
        with open(filepath, 'w') as file:
            LOG.info('saving meta info {} to path {}', data['name'], filepath)
            json.dump(data, file, indent=4, sort_keys=True)

    def remove(self, filepath):
        LOG.debug('removing file {}', filepath)
        os.remove(filepath)

    def move(self, source, destination):
        shutil.move(source, destination)


class ContentRepository(object):

    """
    Handles all content, meaning the stuff that is used to create categories and articles. Categories and sections use
    special file to hold name and description.
    """

    def save(self, filepath, data):
        if not os.path.exists(filepath):
            with open(filepath, 'w') as file:
                file.write(data)
            LOG.info('saving content to path {}', filepath)
        else:
            LOG.info('content at path {} already exists, skipping...', filepath)

    def read(self, filepath):
        with open(filepath, 'r') as file:
            LOG.info('reading content from path {}', filepath)
            return file.read()

    def remove(self, filepath):
        LOG.debug('removing file {}', filepath)
        os.remove(filepath)

    def remove_group(self, filepath):
        LOG.debug('removing folder {}', filepath)
        shutil.rmtree(filepath)

    def move(self, source, destination):
        shutil.move(source, destination)


class ZendeskClient(object):

    """
    Handles all requests to Zendesk
    """
    DEFAULT_URL = 'https://{}.zendesk.com/hc/api/v2/{}'

    def __init__(self, options):
        super().__init__()
        self.options = options

    def url_for(self, path):
        return ZendeskClient.DEFAULT_URL.format(self.options['company_name'], path)

    def _fetch(self, url):
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception('there was a problem fetching data from {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        return response.json()

    def fetch_categories(self):
        url = self.url_for('categories.json')
        LOG.debug('fetching categories from {}', url)
        return self._fetch(url)['categories']

    def fetch_sections(self, category_id):
        url = self.url_for('categories/{}/sections.json'.format(category_id))
        LOG.debug('fetching sections from {}', url)
        return self._fetch(url)['sections']

    def fetch_articles(self, section_id):
        url = self.url_for('sections/{}/articles.json'.format(section_id))
        LOG.debug('fetching articles from {}', url)
        return self._fetch(url)['articles']

    def update_category(self, category):
        return self._update_group(category, 'categories/{}/translations{}.json',
                                  'categories/{}/translations/missing.json')

    def update_section(self, section):
        return self._update_group(section, 'sections/{}/translations{}.json', 'sections/{}/translations/missing.json')

    def update_article(self, article):
        url = 'articles/{}/translations{}.json'
        article_id = article.zendesk_id
        translations = self._article_translations(article.translations)
        missing_url = self.url_for('articles/{}/translations/missing.json'.format(article_id))
        return self._translate(url, missing_url, article_id, translations)

    def _update_group(self, group, url, missing_url):
        group_id = group.zendesk_id
        translations = self._group_translations(group.translations)
        missing_url = self.url_for('sections/{}/translations/missing.json'.format(group_id))
        return self._translate(url, missing_url, group_id, translations)

    def _group_translations(self, translations):
        result = []
        for locale, filepath in translations.items():
            with open(filepath, 'r') as file:
                file_data = json.load(file)
                translation = {
                    'title': file_data['name'],
                    'body': file_data['description'],
                    'locale': locale
                }
                result.append(translation)
        LOG.debug('translations for group {} are {}', filepath, result)
        return result

    def _article_translations(self, translations):
        result = []
        for locale, (body_filepath, content_filepath) in translations.items():
            with open(content_filepath, 'r') as file:
                file_data = json.load(file)
                article_name = file_data['name']
            with open(body_filepath, 'r') as file:
                file_data = file.read()
                article_body = markdown.markdown(file_data)
            translation = {
                'title': article_name,
                'body': article_body,
                'locale': locale
            }
            result.append(translation)
        LOG.debug('translations for article {} are {}', content_filepath, result)
        return result

    def _translate(self, url, missing_url, item_id, translations):
        missing_locales = self._missing_locales(missing_url)
        LOG.debug('missing locales for {} are {}', item_id, missing_locales)
        for translation in translations:
            locale = translation['locale']
            if locale in missing_locales:
                create_url = self.url_for(url.format(item_id, ''))
                LOG.debug('creating translation at {}', create_url)
                self._send_translate_request(create_url, {'translation': translation}, requests.post)
            else:
                update_url = self.url_for(url.format(item_id, '/' + locale))
                LOG.debug('updating translation at {}', update_url)
                self._send_translate_request(update_url, translation, requests.put)

    def _send_translate_request(self, url, translation_data, request_fn):
        response = request_fn(url, data=json.dumps(translation_data),
                              auth=(self.options['user'], self.options['password']),
                              headers={'Content-type': 'application/json'})
        if response.status_code not in [200, 201]:
            raise Exception('there was a problem uploading translations at {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        response_data = response.json()
        return response_data['translation']

    def _missing_locales(self, url):
        response = requests.get(url, auth=(self.options['user'], self.options['password']),
                                headers={'Content-type': 'application/json'})
        if response.status_code != 200:
            raise Exception('there was a problem fetching missng locales from {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        response_data = response.json()
        return response_data['locales']

    def _create(self, url, data):
        response = requests.post(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                                 headers={'Content-type': 'application/json'})
        if response.status_code != 201:
            raise Exception('there was a problem creating an item at {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        return response.json()

    def create_category(self, translations):
        url = self.url_for('categories.json')
        LOG.debug('creating new category at {}', url)
        data = {
            'category': {
                'translations': self._group_translations(translations)
            }
        }
        return self._create(url, data)['category']

    def create_section(self, category_id, translations):
        url = self.url_for('categories/{}/sections.json'.format(category_id))
        LOG.debug('creating new section at {}', url)
        data = {
            'section': {
                'translations': self._group_translations(translations)
            }
        }
        return self._create(url, data)['section']

    def create_article(self, section_id, translations):
        url = self.url_for('sections/{}/articles.json'.format(section_id))
        LOG.debug('creating new article at {}', url)
        data = {
            'article': {
                'translations': self._article_translations(translations)
            }
        }
        return self._create(url, data)['article']

    def delete_article(self, article_id):
        url = self.url_for('articles/{}.json'.format(article_id))
        LOG.debug('deleting article from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        return response.status_code == 200

    def delete_section(self, section_id):
        url = self.url_for('sections/{}.json'.format(section_id))
        LOG.debug('deleting section from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        return response.status_code == 200

    def delete_category(self, category_id):
        url = self.url_for('categories/{}.json'.format(category_id))
        LOG.debug('deleting category from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        return response.status_code == 200

    def move_article(self, article_id, section_id):
        url = self.url_for('articles/{}.json'.format(article_id))
        LOG.debug('moving article {}', url)
        data = {
            'article': {
                'section_id': section_id
            }
        }
        requests.put(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                     headers={'Content-type': 'application/json'})

    def move_section(self, section_id, category_id):
        url = self.url_for('sections/{}.json'.format(section_id))
        LOG.debug('moving section {}', url)
        data = {
            'section': {
                'category_id': category_id
            }
        }
        requests.put(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                     headers={'Content-type': 'application/json'})

    def download_article_attachments(self, article_id, attachments_path):
        url = self.url_for('articles/{}/attachments.json'.format(article_id))
        response = requests.get(url, auth=(self.options['user'], self.options['password']))
        attachments = response.json()
        for attachment in attachments['article_attachments']:
            content_url = attachment['content_url']
            response = requests.get(content_url, stream=True)
            with open(os.path.join(attachments_path, attachment['file_name']), 'w') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)


class WebTranslateItClient(object):

    """
    Handles all reuests to WebTranslateIt
    """
    DEFAULT_URL = 'https://webtranslateit.com/api/projects/{}/{}'

    def __init__(self, options):
        self.api_key = options['webtranslateit_api_key']

    def url_for(self, path):
        return WebTranslateItClient.DEFAULT_URL.format(self.api_key, path)

    def create(self, filepath):
        with open(filepath, 'r') as file:
            normalized_filepath = filepath.replace('\\', '/')
            url = self.url_for('files')
            LOG.debug('upload file {} for transaltion to {}', normalized_filepath, url)
            response = requests.post(url,
                                     data={'file': normalized_filepath, 'name': normalized_filepath},
                                     files={'file': file})
            if response.status_code == 200:
                return str(response.json())
            return None

    def delete(self, file_ids):
        for file_id in file_ids:
            url = self.url_for('files/' + file_id)
            LOG.debug('removing file {} from {}', file_id, url)
            requests.delete(url)

    def move(self, file_id, new_path):
        with open(new_path, 'r') as file:
            normalized_new_path = new_path.replace('\\', '/')
            url = self.url_for('files/{}/locales/en'.format(file_id))
            LOG.debug('update file {} for transaltion', normalized_new_path)
            requests.put(url,
                         data={'file': normalized_new_path, 'name': normalized_new_path},
                         files={'file': file})


class ImportTask(object):

    """
    Imports an existing content from Zendesk. This should only be used to initialize the project. Later on edits
    should be done directly on the files.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)

    def execute(self):
        LOG.info('executing import task...')
        self.create_categories()

    def create_categories(self):
        zendesk_categories = self.zendesk.fetch_categories()
        for zendesk_category in zendesk_categories:
            LOG.debug('creating category {}', zendesk_category['name'])
            category = Group.from_zendesk(self.options['root_folder'], zendesk_category)
            self.create_sections(category)

    def create_sections(self, category):
        zendesk_sections = self.zendesk.fetch_sections(category.zendesk_id)
        for zendesk_section in zendesk_sections:
            LOG.debug('creating section {}', zendesk_section['name'])
            section = Group.from_zendesk(category.path, zendesk_section, category)
            self.create_articles(section)

    def create_articles(self, section):
        zendesk_articles = self.zendesk.fetch_articles(section.zendesk_id)
        for zendesk_article in zendesk_articles:
            LOG.debug('creating article {}', zendesk_article['name'])
            article = Article.from_zendesk(section.path, zendesk_article)
            #TODO uncomment for attachment saving
            #self.zendesk.download_article_attachments(article.zendesk_id, article.attachments_path)


class ExportTask(object):

    """
    Exports content to Zendesk. It will update everything, creating whats missing along the way. Every time this task
    is used the ENTIRE content is uploaded.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)

    def execute(self):
        LOG.info('executing export task...')
        root = self.options['root_folder']
        category_paths = [os.path.join(root, name) for name in os.listdir(root)
                          if not os.path.isfile(os.path.join(root, name))]
        for category_path in category_paths:
            category = Group(category_path)
            category_id = category.zendesk_id
            if category_id:
                LOG.info('exporting category from {}', category.content_filename)
                self.zendesk.update_category(category)
            else:
                LOG.info('exporting new category from {}', category.content_filename)
                new_category = self.zendesk.create_category(category.translations)
                category.meta = new_category
                category_id = new_category['id']

            sections = category.children
            for section in sections:
                section_id = section.zendesk_id
                if section_id:
                    LOG.info('exporting section from {}', section.content_filename)
                    self.zendesk.update_section(section)
                else:
                    LOG.info('exporting new section from {}', section.content_filename)
                    new_section = self.zendesk.create_section(category_id, section.translations)
                    section.meta = new_section
                    section_id = new_section['id']
                articles = section.children
                for article in articles:
                    article_id = article.zendesk_id
                    if article_id:
                        LOG.info('exporting article {} from {}', article.name, article.path)
                        self.zendesk.update_article(article)
                    else:
                        LOG.info('exporting new article {} from {}', article.name, article.path)
                        new_article = self.zendesk.create_article(section_id, article.translations)
                        article.meta = new_article


class TranslateTask(object):

    """
    Upload content to WebTranslateIt. Should only be used to upload the initial conent in the default language after
    it has been imported from Zendesk.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.translate = WebTranslateItClient(options)

    def execute(self):
        LOG.info('executing translate task...')
        root = self.options['root_folder']
        for filepath in os.listdir(root):
            category_path = os.path.join(root, filepath)
            if os.path.isdir(category_path):
                category = Group(category_path)
                LOG.info('upload {} for transaltion', category.content_filename)
                category_translate_id = self.translate.create(category.content_filename)
                category_meta = category.meta
                category_meta.update({'webtranslateit_ids': [category_translate_id]})
                category.meta = category_meta
                for section in category.children:
                    LOG.info('upload {} for transaltion', section.content_filename)
                    section_translate_id = self.translate.create(section.content_filename)
                    section_meta = section.meta
                    section_meta.update({'webtranslateit_ids': [section_translate_id]})
                    section.meta = section_meta
                    for article in section.children:
                        LOG.info('upload {} for transaltion', article.content_filename)
                        content_translate_id = self.translate.create(article.content_filename)
                        LOG.info('upload {} for transaltion', article.body_filename)
                        body_translate_id = self.translate.create(article.body_filename)
                        article_meta = article.meta
                        article_meta.update({'webtranslateit_ids': [body_translate_id, content_translate_id]})
                        article.meta = article_meta


class RemoveTask(object):

    """
    Removes articles, sections and categories.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.translate = WebTranslateItClient(options)

    def execute(self):
        LOG.info('executing delete task...')
        path = self.options['path']
        if not os.path.exists(path):
            raise ValueError('Path to be deleted must exists, but {} doesn\'t'.format(path))

        if os.path.isfile(path):
            article_name, _ = os.path.splitext(os.path.basename(path))
            article_dir = os.path.dirname(path)
            self._delete_article(Article(article_dir, article_name))
        else:
            self._delete_group(path)

    def _delete_group(self, path):
        LOG.info('deleting group from {}', path)
        category, section = Group.from_path(self.options['root'], path)
        if section:
            group = section
            for article in group.children:
                self._delete_article(article)
        else:
            group = category
            for section in group.children:
                self._delete_group(section.path)
        self.zendesk.delete_section(group.zendesk_id)
        self.translate.delete(group.translate_ids)
        group.remove()

    def _delete_article(self, article):
        LOG.info('deleting article {} from {}', article.name, article.path)
        article_id = article.zendesk_id
        if article_id:
            self.zendesk.delete_article(article.zendesk_id)
        self.translate.delete(article.translate_ids)
        article.remove()


class MoveTask(object):

    """
    Move article to a different section/category
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.translate = WebTranslateItClient(options)

    def execute(self):
        source = self.options['source']
        destination = self.options['destination']
        article = None
        group = None

        if os.path.isfile(source):
            article_name, _ = os.path.splitext(os.path.basename(source))
            article_dir = os.path.dirname(source)
            article = Article(article_dir, article_name)
        else:
            category = Group(os.path.dirname(source))
            group = Group(source, category)

        dest_category, dest_section = Group.from_path(self.options['root'], destination)

        if article and not dest_section:
            raise ValueError('Cant move article {} to category {}, please specify a section'
                             .format(article.name, dest_category.path))

        if article:
            LOG.info('moving article {} to section {}', article.name, dest_section.path)
            body_translate_id, content_translate_id = article.translate_ids
            self.zendesk.move_article(article.zendesk_id, dest_section.zendesk_id)
            article.move_to(dest_section)
            self.translate.move(body_translate_id, article.body_filename)
            self.translate.move(content_translate_id, article.content_filename)
        elif group:
            LOG.info('moving section {} to category {}', group.path, dest_category.path)
            content_translate_id, = group.translate_ids
            self.zendesk.move_section(group.zendesk_id, dest_category.zendesk_id)
            group.move_to(dest_category)
            for article in group.children:
                LOG.info('moving article {} in translations', article.name)
                body_translate_id, content_translate_id = article.translate_ids
                self.translate.move(body_translate_id, article.body_filename)
                self.translate.move(content_translate_id, article.content_filename)
            self.translate.move(content_translate_id, group.content_filename)

        else:
            raise ValueError('Neither section nor article was specified as source. please check the path {}'
                             .format(source))


class DoctorTask(object):

    """
    Verifies if everything is valid and creates missing files.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options

    def execute(self):
        LOG.info('executing doctor task...')
        root = self.options['root_folder']
        category_paths = [os.path.join(root, name) for name in os.listdir(root)
                          if not os.path.isfile(os.path.join(root, name))]
        for category_path in category_paths:
            category = Group(category_path)
            category.fixme()
            for section in category.children:
                section.fixme()
                for article in section.children:
                    article.fixme()


tasks = {
    'import': ImportTask,
    'export': ExportTask,
    'translate': TranslateTask,
    'remove': RemoveTask,
    'move': MoveTask,
    'doctor': DoctorTask
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', help='Increase output verbosity',
                        action='store_true')
    parser.add_argument('-r', '--root',
                        help='Article\'s root folder',
                        default='help_center_content')
    subparsers = parser.add_subparsers(help='Task to be performed.', dest='task')

    task_parsers = {task_parser: subparsers.add_parser(task_parser) for task_parser in tasks}

    task_parsers['remove'].add_argument('path', help='Set path for removing an item')

    task_parsers['move'].add_argument('source', help='Set source section/article')
    task_parsers['move'].add_argument('destination', help='Set destination category/section')

    return parser.parse_args()


def parse_options():
    config = configparser.ConfigParser()
    config.read('translator.config')

    return {
        'root_folder': config['default']['root_folder'],
        'company_name': config['default']['company_name'],
        'user': config['default']['user'],
        'password': config['default']['password'],
        'webtranslateit_api_key': config['default']['webtranslateit_api_key']
    }


def resolve_args(args, options):
    task = tasks[args.task](options)
    LOG.verbose = args.verbose

    for key, value in vars(args).items():
        options[key] = value

    return task, options


def main():
    args = parse_args()
    options = parse_options()
    task, options = resolve_args(args, options)
    task.execute()


if __name__ == '__main__':
    main()
