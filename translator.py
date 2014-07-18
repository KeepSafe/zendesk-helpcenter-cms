"""
    translator
    ~~~~~~~~~~

    Manages zendesk help center translation.

    :copyright: (c) 2014 by KeepSafe.
"""
import argparse
import json
import os
import re
import html2text
import markdown
import requests
import unicodedata


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and underscores) and converts spaces to
    hyphens. Also strips leading and trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


class Logger(object):
    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose

    def log(self, message, *args):
        if self.verbose:
            print(message.format(*args))


LOGGER = Logger()


class MetaRepository(object):
    # TODO possible name conflicts with articles
    META_GROUP_FILENAME = '__group__.meta'
    META_EXTENSION = '.meta'

    def _group_filepath(self, path):
        return os.path.join(path, MetaRepository.META_GROUP_FILENAME)

    def _read_group(self, path):
        filepath = self._group_filepath(path)
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                return json.load(file)
        return None

    def save_group(self, group, path):
        with open(self._group_filepath(path), 'w') as file:
            json.dump(group, file, indent=4, sort_keys=True)

    def save_article(self, article, path):
        with open(os.path.join(path, article['name']) + MetaRepository.META_EXTENSION, 'w') as file:
            json.dump(article, file, indent=4, sort_keys=True)

    def group_id(self, path):
        data = self._read_group(path)
        return data['id'] if data else None

    def article_id(self, path, article_name):
        filepath = os.path.join(path, article_name + MetaRepository.META_EXTENSION)
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                data = json.load(file)
                return data['id']
        return None

    def is_category(self, path):
        data = self._read_group(path)
        return 'category_id' not in data

    def get_articles(self, files):
        return [article for article in files if
                article.endswith(MetaRepository.META_EXTENSION) and article != MetaRepository.META_GROUP_FILENAME]


class ContentRepository(object):
    CONTENT_FILENAME = '__group__.json'
    CONTENT_EXTENSION = '.md'

    def __init__(self):
        super().__init__()
        self.meta = MetaRepository()

    def is_content(self, name):
        return name == ContentRepository.CONTENT_FILENAME

    def save_group(self, group, path):
        group_path = os.path.join(path, group['name'])
        os.makedirs(group_path, exist_ok=True)
        group_content = {
            'name': group['name'],
            'description': group['description']
        }
        with open(os.path.join(group_path, ContentRepository.CONTENT_FILENAME), 'w') as file:
            json.dump(group_content, file, indent=4, sort_keys=True)
        return group_path

    def save_article(self, article, group_path):
        filename = os.path.join(group_path, article['name'] + ContentRepository.CONTENT_EXTENSION)
        with open(filename, 'w') as file:
            file_content = html2text.html2text(article['body'])
            file.write(file_content)
        return filename

    def get_translated_group(self, files):
        result = {}
        master_name, master_ext = os.path.splitext(ContentRepository.CONTENT_FILENAME)
        for file in files:
            if file == ContentRepository.CONTENT_FILENAME:
                result['en-us'] = file
            else:
                name, ext = os.path.splitext(file)
                if name.startswith(master_name + '.') and ext == master_ext:
                    locale = name.split('.')[-1]
                    result[locale] = file
        return result

    def get_translated_articles(self, files):
        result = {}
        meta_articles = self.meta.get_articles(files)
        for meta_article in meta_articles:
            meta_name, _ = os.path.splitext(meta_article)
            translated_articles = {}
            articles = [article for article in files if
                        article.startswith(meta_name) and article.endswith(ContentRepository.CONTENT_EXTENSION)]
            for article in articles:
                if article == meta_name + ContentRepository.CONTENT_EXTENSION:
                    translated_articles['en-us'] = article
                else:
                    name, ext = os.path.splitext(article)
                    if name.startswith(meta_name + '.') and ext == ContentRepository.CONTENT_EXTENSION:
                        locale = name.split('.')[-1]
                        translated_articles[locale] = article
            result[meta_name] = translated_articles
        return result


class ZendeskClient(object):
    DEFAULT_URL = 'https://{}.zendesk.com/hc/api/v2/{}'

    def __init__(self, options):
        super().__init__()
        self.options = options

    def url_for(self, path):
        return ZendeskClient.DEFAULT_URL.format(self.options['company_name'], path)

    def fetch_categories(self):
        response = requests.get(self.url_for('categories.json'))
        response_data = response.json()
        return response_data['categories'] if response_data else []

    def fetch_sections(self, category_id):
        response = requests.get(self.url_for('categories/{}/sections.json'.format(category_id)))
        response_data = response.json()
        return response_data['sections'] if response_data else []

    def fetch_articles(self, section_id):
        response = requests.get(self.url_for('sections/{}/articles.json'.format(section_id)))
        response_data = response.json()
        return response_data['articles'] if response_data else []

    def _translate_group(self, url, translations, request_fn):
        result = []
        for translation in translations:
            response = request_fn(url, data=json.dumps({'translation': translation}),
                                  auth=(self.options['user'], self.options['password']),
                                  headers={'Content-type': 'application/json'})
            response_data = response.json()
            result.append(response_data['translation'])
        return result

    def create_category_translation(self, category_id, translations):
        url = self.url_for('categories/{}/translations.json'.format(category_id))
        return self._translate_group(url, translations, requests.post)

    def create_section_translation(self, section_id, translations):
        url = self.url_for('sections/{}/translations.json'.format(section_id))
        return self._translate_group(url, translations, requests.post)

    def create_article_translation(self, article_id, translations):
        url = self.url_for('articles/{}/translations.json'.format(article_id))
        return self._translate_group(url, translations, requests.post)

    def update_category_translation(self, category_id, translations):
        url = self.url_for('categories/{}/translations.json'.format(category_id))
        return self._translate_group(url, translations, requests.put)

    def update_section_translation(self, section_id, translations):
        url = self.url_for('sections/{}/translations.json'.format(section_id))
        return self._translate_group(url, translations, requests.put)

    def update_article_translation(self):
        pass


class WebTranslateItClient(object):
    DEFAULT_URL = 'https://webtranslateit.com/api/projects/{}/{}'
    API_KEY = 'pDLsTA3XPlO0rfRbTFroAw'

    def url_for(self, path):
        return WebTranslateItClient.DEFAULT_URL.format(WebTranslateItClient.API_KEY, path)

    def create_file(self, filepath):
        with open(filepath, 'r') as file:
            linux_filepath = filepath.replace('\\', '/')
            # TODO handle response
            response = requests.post(self.url_for('files'), data={'file': linux_filepath, 'name': linux_filepath},
                                     files={'file': file})


class ImportTask(object):
    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.repository = ContentRepository()
        self.meta = MetaRepository()

    def execute(self):
        self.create_categories()

    def create_categories(self):
        categories = self.zendesk.fetch_categories()
        for category in categories:
            category_path = self.repository.save_group(category, self.options['root_folder'])
            self.meta.save_group(category, category_path)
            self.create_sections(category['id'], category_path)

    def create_sections(self, category_id, category_path):
        sections = self.zendesk.fetch_sections(category_id)
        for section in sections:
            section_path = self.repository.save_group(section, category_path)
            self.meta.save_group(section, section_path)
            self.create_articles(section['id'], section_path)

    def create_articles(self, section_id, section_path):
        articles = self.zendesk.fetch_articles(section_id)
        for article in articles:
            self.repository.save_article(article, section_path)
            self.meta.save_article(article, section_path)


class ExportTask(object):
    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
        self.meta = MetaRepository()
        self.repo = ContentRepository()

    def execute(self):
        for root, _, files in os.walk(self.options['root_folder']):
            group_id, group_translations = self._translated_group(root, files)
            if group_id:
                if self.meta.is_category(root):
                    self.zendesk.create_category_translation(group_id, group_translations)
                else:
                    self.zendesk.create_section_translation(group_id, group_translations)
            articles = self._translated_articles(root, files)
            for article_id, article_translations in articles.items():
                self.zendesk.create_article_translation(article_id, article_translations)

    def _translated_group(self, path, files):
        result = []
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
        return group_id, result

    def _translated_articles(self, path, files):
        result = {}
        articles = self.repo.get_translated_articles(files)
        for article_name, article_details in articles.items():
            article_id = self.meta.article_id(path, article_name)
            for locale, article_filename in article_details.items():
                with open(os.path.join(path, article_filename), 'r') as file:
                    article_body = file.read()
                    translation = {
                        'title': article_name,
                        'body': markdown.markdown(article_body),
                        'locale': locale
                    }
                    translations = result.get(article_id, [])
                    translations.append(translation)
                    result[article_id] = translations
        return result


class TranslateTask(object):
    TRANSLATE_EXTENSIONS = ['.md']

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.translate = WebTranslateItClient()
        self.meta = MetaRepository()
        self.repo = ContentRepository()

    def is_file_to_translate(self, path):
        _, ext = os.path.splitext(path)
        name = os.path.basename(path)
        return ext in TranslateTask.TRANSLATE_EXTENSIONS or self.repo.is_content(name)

    def execute(self):
        for root, _, files in os.walk(self.options['root_folder']):
            files = filter(self.is_file_to_translate, files)
            for file in files:
                self.translate.create_file(os.path.join(root, file))


tasks = {
    'import': ImportTask,
    'export': ExportTask,
    'translate': TranslateTask
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('task',
                        help='Task to be performed.',
                        choices=tasks.keys())
    parser.add_argument('-f', '--force',
                        help='Ignore warnings and override existing files.',
                        action='store_true')
    parser.add_argument('-v', '--verbose', help='Increase output verbosity',
                        action='store_true')
    parser.add_argument('-r', '--root',
                        help='Article\'s root folder',
                        default='help_center_content')
    return parser.parse_args()


def parse_options():
    return {
        'root_folder': 'help_center_content',
        'company_name': 'testingzendesk12',
        'user': 'zendesk@maildrop.cc',
        'password': '123zendesk'
    }


def resolve_args(args, options):
    task = tasks[args.task](options)
    LOGGER.verbose = args.verbose

    return task, options


def main():
    args = parse_args()
    options = parse_options()
    task, options = resolve_args(args, options)
    task.execute()


if __name__ == '__main__':
    main()
