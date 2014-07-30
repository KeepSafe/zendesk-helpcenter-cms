"""
    translator
    ~~~~~~~~~~

    Manages zendesk help center translation.

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


def to_json(data):
    return json.dumps(data, indent=4, sort_keys=True)


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
        pass


LOG = Logger()


class Group(object):

    def __init__(self, name, path, parent=None):
        self.meta_repo = MetaRepository()
        self.content = ContentRepository()
        self.name = name
        self.path = path
        self.parent = parent

    def _articles(self):
        filepaths = [filepath for filepath in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, filepath))]
        article_names = filter(lambda a: a.endswith('.md'), filepaths)
        article_names_bits = map(lambda a: a.split('.'), article_names)
        article_names_bits = filter(lambda a: len(a) == 2, article_names_bits)
        article_names = map(lambda a: a[0], article_names_bits)
        articles = [Article.from_path(self.path, article_name) for article_name in article_names]
        print(articles)
        return articles

    def _subgroups(self):
        filepaths = [filepath for filepath in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, filepath))]
        return [Group.from_path(os.path.join(self.path, filepath), self) for filepath in filepaths]

    @property
    def meta(self):
        path = os.path.join(self.path, '.group.meta')
        data = to_json({'zendesk_id': self.zendesk_id})
        return [(path, data)]

    @property
    def contents(self):
        data = to_json({
            'name': self.name,
            'description': self.description
        })
        return [
            (os.path.join(self.path, '__group__.json'), data)
        ]

    @property
    def children(self):
        if self.parent:
            return self._articles()
        else:
            return self._subgroups()

    def save(self):
        os.makedirs(self.path, exist_ok=True)
        self.meta_repo.save(self)
        self.content.save(self)

    def delete(self):
        pass

    def move(self):
        pass

    def translate(self):
        print('translating: ' + self.name)

    @staticmethod
    def from_zendesk(parent_path, zendesk_group, parent=None):
        name = zendesk_group['name']
        path = os.path.join(parent_path, name)
        group = Group(name, path, parent)
        group.zendesk_id = zendesk_group['id']
        group.description = zendesk_group['description']
        return group

    @staticmethod
    def from_path(path, parent=None):
        if not os.path.exists(path):
            raise ValueError('given path {} does not exist'.format(path))
        if not os.path.isdir(path):
            raise ValueError('given path {} is not a directory'.format(path))
        return Group(os.path.basename(path), path, parent)


class Article(object):

    def __init__(self, name, body, path):
        self.meta_repo = MetaRepository()
        self.content = ContentRepository()
        self.name = name
        self.body = body
        self.path = path
        self.translations = {}

    @property
    def meta(self):
        return [(self.meta_filename(self.path, self.name), to_json({'zendesk_id': self.zendesk_id}))]

    @property
    def contents(self):
        return [
            (self.body_filename(self.path, self.name), self.body),
            (self.name_filename(self.path, self.name), to_json({'name': self.name}))
        ]

    def save(self):
        self.meta_repo.save(self)
        self.content.save(self)

    def delete(self):
        pass

    def move(self):
        pass

    def translate(self):
        print('translating: ' + self.name)

    @staticmethod
    def body_filename(path, name):
        return os.path.join(path, '{}.md'.format(name))

    @staticmethod
    def name_filename(path, name):
        return os.path.join(path, '{}.json'.format(name))

    @staticmethod
    def meta_filename(path, name):
        return os.path.join(path, '.article_{}.meta'.format(name))

    @staticmethod
    def from_zendesk(section_path, zendesk_article):
        name = zendesk_article['name']
        body = html2text.html2text(zendesk_article['body'])
        article = Article(name, body, section_path)
        article.zendesk_id = zendesk_article['id']
        return article

    @staticmethod
    def from_path(path, article_name):
        article_filepath = Article.body_filename(path, article_name)
        if not os.path.exists(path):
            raise ValueError('given path {} does not exist'.format(article_filepath))
        if not os.path.isdir(path):
            raise ValueError('given path {} is not a directory'.format(article_filepath))
        body = ContentRepository().read(article_filepath)
        return Article(article_name, body, path)


class MetaRepository(object):

    """
    Handles all meta content, meaning the content coming from Zendesk. Normally just dumps json from Zendesk to a file
    and reads whatever is needed from there. Also has some utility methods which requite meta info.
    """

    def read(self, item):
        filepath = item.meta_filename
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                LOG.debug('reading meta {}', filepath)
                return json.load(file)
        LOG.debug('unable to read meta {}', filepath)
        return None

    def save(self, item):
        for filepath, data in item.meta:
            if not os.path.exists(filepath):
                with open(filepath, 'w') as file:
                    LOG.info('saving meta info {} to path {}', item.name, filepath)
                    json.dump(data, file, indent=4, sort_keys=True)
            else:
                LOG.info('meta info {} at path {} already exists, skipping...', item.name, filepath)

    def delete(self, item):
        filepath = item.meta_filepath
        LOG.debug('removing file {}', filepath)
        os.remove(filepath)


class ContentRepository(object):

    """
    Handles all content, meaning the stuff that is used to create categories and articles. Categories and sections use
    special file to hold name and description.
    """

    def __init__(self):
        super().__init__()
        self.meta = MetaRepository()

    def is_content(self, name):
        return name.endswith(ContentRepository.CONTENT_NAME_EXTENSION) or name == ContentRepository.CONTENT_GROUP_FILENAME

    def save(self, item):
        for filepath, data in item.contents:
            if not os.path.exists(filepath):
                with open(filepath, 'w') as file:
                    file.write(data)
                LOG.info('saving content {} to path {}', item.name, filepath)
            else:
                LOG.info('content {} at path {} already exists, skipping...', item.name, filepath)

    def read(self, item):
        results = {}
        for filepath in item.content_filepaths:
            with open(filepath, 'r') as file:
                results[filepath] = file.read()
        return results

    def get_translated_group(self, files):
        result = {}
        master_name, master_ext = os.path.splitext(ContentRepository.CONTENT_GROUP_FILENAME)
        for file in files:
            if file == ContentRepository.CONTENT_GROUP_FILENAME:
                # TODO make default external and configurable
                result['en-us'] = file
            else:
                name, ext = os.path.splitext(file)
                if name.startswith(master_name + '.') and ext == master_ext:
                    locale = name.split('.')[-1]
                    result[locale] = file

        return result

    def get_translated_articles(self, files):
        result = {}
        article_names = filter(lambda a: a.endswith(ContentRepository.CONTENT_BODY_EXTENSION), files)
        article_names_bits = map(lambda a: a.split('.'), article_names)
        article_names_bits = filter(lambda a: len(a) == 2, article_names_bits)
        article_names = map(lambda a: a[0], article_names_bits)

        for article_name in article_names:
            translated_articles = {}
            articles = [article for article in files if
                        article.startswith(article_name) and article.endswith(ContentRepository.CONTENT_BODY_EXTENSION)]
            for article in articles:
                if article == article_name + ContentRepository.CONTENT_BODY_EXTENSION:
                    translated_articles['en-us'] = article
                else:
                    name, ext = os.path.splitext(article)
                    if name.startswith(article_name + '.') and ext == ContentRepository.CONTENT_BODY_EXTENSION:
                        locale = name.split('.')[-1]
                        translated_articles[locale] = article
            result[article_name] = translated_articles
        return result

    def delete_article(self, article_dir, article_name):
        files = [f for f in os.listdir(article_dir)]
        files = map(lambda f: f.split('.'), files)
        files = filter(lambda f: f[0] == article_name, files)
        files = map(lambda f: '.'.join(f), files)
        for article in files:
            path = os.path.join(article_dir, article)
            LOG.debug('removeing file {}', path)
            os.remove(path)

    def delete_group(self, path):
        shutil.rmtree(path)

    def article_translated_name(self, path, filename):
        name, _ = os.path.splitext(filename)
        with open(os.path.join(path, name + ContentRepository.CONTENT_NAME_EXTENSION)) as file:
            file_data = json.load(file)
            return file_data['name']


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
            raise Exception('there was a problem fetching data from {}. status was {} and message {}', url,
                            response.status_code, response.text)
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

    def update_category(self, category_id, translations):
        url = 'categories/{}/translations{}.json'
        missing_url = self.url_for('categories/{}/translations/missing.json'.format(category_id))
        return self._translate(url, missing_url, category_id, translations)

    def update_section(self, section_id, translations):
        url = 'sections/{}/translations{}.json'
        missing_url = self.url_for('sections/{}/translations/missing.json'.format(section_id))
        return self._translate(url, missing_url, section_id, translations)

    def update_article(self, article_id, translations):
        url = 'articles/{}/translations{}.json'
        missing_url = self.url_for('articles/{}/translations/missing.json'.format(article_id))
        return self._translate(url, missing_url, article_id, translations)

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
                LOG.debug('creating translation at {}', update_url)
                self._send_translate_request(update_url, translation, requests.put)

    def _send_translate_request(self, url, translation_data, request_fn):
        response = request_fn(url, data=json.dumps(translation_data),
                              auth=(self.options['user'], self.options['password']),
                              headers={'Content-type': 'application/json'})
        if response.status_code not in [200, 201]:
            raise Exception('there was a problem uploading translations at {}. status was {} and message {}', url,
                            response.status_code, response.text)
        response_data = response.json()
        return response_data['translation']

    def _missing_locales(self, url):
        response = requests.get(url, auth=(self.options['user'], self.options['password']),
                                headers={'Content-type': 'application/json'})
        if response.status_code != 200:
            raise Exception('there was a problem fetching missng locales from {}. status was {} and message {}', url,
                            response.status_code, response.text)
        response_data = response.json()
        return response_data['locales']

    def _create(self, url, data):
        response = requests.post(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                                 headers={'Content-type': 'application/json'})
        if response.status_code != 201:
            raise Exception('there was a problem creating an item at {}. status was {} and message {}', url,
                            response.status_code, response.text)
        return response.json()

    def create_category(self, translations):
        url = self.url_for('categories.json')
        LOG.debug('creating new category at {}', url)
        data = {
            'category': {
                'translations': translations
            }
        }
        return self._create(url, data)['category']

    def create_section(self, category_id, translations):
        url = self.url_for('categories/{}/sections.json'.format(category_id))
        LOG.debug('creating new section at {}', url)
        data = {
            'section': {
                'translations': translations
            }
        }
        return self._create(url, data)['section']

    def create_article(self, section_id, translations):
        url = self.url_for('sections/{}/articles.json'.format(section_id))
        LOG.debug('creating new article at {}', url)
        data = {
            'article': {
                'translations': translations
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


class WebTranslateItClient(object):

    """
    Handles all reuests to WebTranslateIt
    """
    DEFAULT_URL = 'https://webtranslateit.com/api/projects/{}/{}'

    def __init__(self, options):
        self.api_key = options['webtranslateit_api_key']

    def url_for(self, path):
        return WebTranslateItClient.DEFAULT_URL.format(self.api_key, path)

    def create_file(self, filepath):
        with open(filepath, 'r') as file:
            linux_filepath = filepath.replace('\\', '/')
            # TODO handle response
            response = requests.post(self.url_for('files'), data={'file': linux_filepath, 'name': linux_filepath},
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
        self.repository = ContentRepository()
        self.meta = MetaRepository()

    def execute(self):
        LOG.info('executing import task...')
        self.create_categories()

    def create_categories(self):
        zendesk_categories = self.zendesk.fetch_categories()
        for zendesk_category in zendesk_categories:
            LOG.debug('creating category {}', zendesk_category['name'])
            category = Group.from_zendesk(self.options['root_folder'], zendesk_category)
            category.save()
            category.sections = self.create_sections(category)

    def create_sections(self, category):
        zendesk_sections = self.zendesk.fetch_sections(category.zendesk_id)
        for zendesk_section in zendesk_sections:
            LOG.debug('creating section {}', zendesk_section['name'])
            section = Group.from_zendesk(category.path, zendesk_section, category)
            section.save()
            self.create_articles(section)

    def create_articles(self, section):
        zendesk_articles = self.zendesk.fetch_articles(section.zendesk_id)
        for zendesk_article in zendesk_articles:
            LOG.debug('creating article {}', zendesk_article['name'])
            article = Article.from_zendesk(section.path, zendesk_article)
            article.save()


class ExportTask(object):

    """
    Exports content to Zendesk. It will update everything, creating whats missing along the way. Every time this task
    is used the ENTIRE content is uploaded.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.meta = MetaRepository()
        self.repo = ContentRepository()

    def execute(self):
        LOG.info('executing export task...')
        root = self.options['root_folder']
        category_paths = [os.path.join(root, name) for name in os.listdir(root)
                          if not os.path.isfile(os.path.join(root, name))]
        for category_path in category_paths:
            category_id, category_translations = self._translated_group(category_path)
            if category_id:
                LOG.info('exporting category {} from {}', category_id, root)
                self.zendesk.update_category(category_id, category_translations)
            else:
                LOG.info('exporting new category from {}', root)
                new_category = self.zendesk.create_category(category_translations)
                self.meta.save_group(new_category, category_path)
                category_id = new_category['id']

            section_paths = [os.path.join(category_path, name) for name in os.listdir(category_path)
                             if not os.path.isfile(os.path.join(category_path, name))]
            for section_path in section_paths:
                section_id, section_translations = self._translated_group(section_path)
                if section_id:
                    LOG.info('exporting section {} from {}', section_id, category_path)
                    self.zendesk.update_section(section_id, section_translations)
                else:
                    LOG.info('exporting new section from {}', category_path)
                    new_section = self.zendesk.create_section(category_id, section_translations)
                    self.meta.save_group(new_section, section_path)
                    section_id = new_section['id']
                articles = self._translated_articles(section_path)
                for article_id, article_translations in articles.items():
                    if article_id:
                        LOG.info('exporting article {} from {}', article_id, section_path)
                        self.zendesk.update_article(article_id, article_translations)
                    else:
                        # TODO add real article name
                        LOG.info('exporting new article from {}', section_path)
                        new_article = self.zendesk.create_article(section_id, article_translations)
                        self.meta.save_article(new_article, section_path)

    def _translated_group(self, path):
        result = []
        files = [f for f in os.listdir(path)]
        group = self.repo.get_translated_group(files)
        group_id = self.meta.group_id(path)
        for locale, filename in group.items():
            with open(os.path.join(path, filename), 'r') as file:
                file_data = json.load(file)
                translation = {
                    'title': file_data['name'],
                    'body': file_data['description'],
                    'locale': locale
                }
                result.append(translation)
        LOG.debug('translations for group {} are {}', path, result)
        return group_id, result

    def _translated_articles(self, path):
        result = {}
        files = [f for f in os.listdir(path)]
        articles = self.repo.get_translated_articles(files)
        for article_name, article_details in articles.items():
            article_id = self.meta.article_id(path, article_name)
            for locale, article_filename in article_details.items():
                article_translated_name = self.repo.article_translated_name(path, article_filename)
                with open(os.path.join(path, article_filename), 'r') as file:
                    article_body = file.read()
                    translation = {
                        'title': article_translated_name,
                        'body': markdown.markdown(article_body),
                        'locale': locale
                    }
                    translations = result.get(article_id, [])
                    translations.append(translation)
                    result[article_id] = translations
            LOG.debug('translations for article {} are {}', article_name, result[article_id])
        return result


class TranslateTask(object):

    """
    Upload content to WebTranslateIt. Should only be used to upload the initial conent in the default language after
    it has been imported from Zendesk.
    """
    TRANSLATE_EXTENSIONS = ['.md']

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.translate = WebTranslateItClient(options)
        self.meta = MetaRepository()
        self.repo = ContentRepository()

    def execute(self):
        LOG.info('executing translate task...')
        root = self.options['root_folder']
        for filepath in os.listdir(root):
            category_path = os.path.join(root, filepath)
            if os.path.isdir(category_path):
                category = Group.from_path(category_path)
                category.translate()
                for section in category.children:
                    section.translate()
                    for article in section.children:
                        article.translate()


class RemoveTask(object):

    """
    Removes articles, sections and categories.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.translate = WebTranslateItClient(options)
        self.meta = MetaRepository()
        self.repo = ContentRepository()

    def execute(self):
        LOG.info('executing delete task...')
        path = self.options['path']
        if not os.path.exists(path):
            raise ValueError('Path to be deleted must exists, but {} doesn\'t'.format(path))

        if os.path.isfile(path):
            self._delete_article(path)
        else:
            self._delete_group(path)

    def _delete_group(self, path):
        group_id = self.meta.group_id(path)
        LOG.info('deleting group {} from {}', group_id, path)
        if self.meta.is_category(path):
            self.zendesk.delete_category(group_id)
        else:
            self.zendesk.delete_section(group_id)
        self.translate.delete_file(path)
        self.repo.delete_group(path)

    def _delete_article(self, path):
        article_name, _ = os.path.splitext(os.path.basename(path))
        article_dir = os.path.dirname(path)
        article_id = self.meta.article_id(article_dir, article_name)
        LOG.info('deleting article {} from {}', article_name, path)
        self.zendesk.delete_article(article_id)
        self.translate.delete_file(path)
        self.meta.delete_article(article_dir, article_name)
        self.repo.delete_article(article_dir, article_name)


class AddTask(object):

    """
    Creates default files when adding new article in a new category/section
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.repo = ContentRepository()

    def execute(self):
        path = self.options['path']
        article_path = os.path.dirname(path)
        article_name, _ = os.path.splitext(os.path.basename(path))
        section_path = os.path.dirname(article_path)
        section_name = os.path.basename(article_path)
        category_path = os.path.dirname(section_path)
        category_name = os.path.basename(section_path)
        self.repo.save_group({'name': category_name, 'description': ''}, category_path)
        self.repo.save_group({'name': section_name, 'description': ''}, section_path)
        self.repo.save_article({'name': article_name, 'body': ''}, article_path)


class MoveTask(object):

    """
    Move article to a different section/category
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.translate = WebTranslateItClient(options)
        self.meta = MetaRepository()
        self.repo = ContentRepository()

    def execute(self):
        source = self.options['source']
        destination = self.options['destination']

        self.translate.move(source, destination)
        self.zendesk.move(source, destination)
        self.meta.move(source, destination)
        self.repo.move(source, destination)


class DoctorTask(object):

    """
    Verifies if everything is valid and creates missing files.
    """

    def execute(self):


tasks = {
    'import': ImportTask,
    'export': ExportTask,
    'translate': TranslateTask,
    'remove': RemoveTask,
    'add': AddTask,
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

    task_parsers['remove'].add_argument('-p', '--path', help='Set path for removing an item')
    task_parsers['add'].add_argument('-p', '--path', help='Set path for removing an item')

    task_parsers['move'].add_argument('-s', '--source', help='Set source category/section/article')
    task_parsers['move'].add_argument('-d', '--destination', help='Set destination category/section/article')

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
