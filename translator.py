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


class Logger(object):

    """
    Logs messages to stdout. Has 2 levels, info and debug, with debug only being used if verbose id True.
    """

    def __init__(self, verbose=False):
        super().__init__()
        self.verbose = verbose

    def debug(self, message, *args):
        if self.verbose:
            print(message.format(*args))

    def info(self, message, *args):
        #print(message.format(*args))
        pass


LOG = Logger()


class MetaRepository(object):

    """
    Handles all meta content, meaning the content coming from Zendesk. Normally just dumps json from Zendesk to a file
    and reads whatever is needed from there. Also has some utility methods which requite meta info.
    """
    # TODO possible name conflicts with articles
    META_GROUP_FILENAME = '__group__.meta'
    META_EXTENSION = '.meta'

    def _group_filepath(self, path):
        return os.path.join(path, MetaRepository.META_GROUP_FILENAME)

    def _read_group(self, path):
        filepath = self._group_filepath(path)
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                LOG.debug('reading group meta {}', filepath)
                return json.load(file)
        LOG.debug('unable to read group meta {}', filepath)
        return None

    def save_group(self, group, path):
        meta_path = self._group_filepath(path)
        with open(meta_path, 'w') as file:
            LOG.info('saving group meta info {} to path {}', group['name'], meta_path)
            json.dump(group, file, indent=4, sort_keys=True)

    def save_article(self, article, path):
        meta_path = os.path.join(path, article['name'] + MetaRepository.META_EXTENSION)
        with open(meta_path, 'w') as file:
            LOG.info('saving article meta info {} to path {}', article['name'], meta_path)
            json.dump(article, file, indent=4, sort_keys=True)

    def group_id(self, path):
        data = self._read_group(path)
        return data['id'] if data else None

    def article_id(self, path, article_name):
        filepath = os.path.join(path, article_name + MetaRepository.META_EXTENSION)
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                LOG.debug('reading article meta {}', filepath)
                data = json.load(file)
                return data['id']
        LOG.debug('unable to read article meta {}', filepath)
        return None

    def is_category(self, path):
        data = self._read_group(path)
        return 'category_id' not in data

    def delete_article(self, article_dir, article_name):
        path = os.path.join(article_dir, article_name + MetaRepository.META_EXTENSION)
        LOG.debug('removing file {}', path)
        os.remove(path)


class ContentRepository(object):

    """
    Handles all content, meaning the stuff that is used to create categories and articles. Categories and sections use
    special file to hold name and description.
    """
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
        content_path = os.path.join(group_path, ContentRepository.CONTENT_FILENAME)
        with open(content_path, 'w') as file:
            LOG.info('saving group content {} to path {}', group['name'], content_path)
            json.dump(group_content, file, indent=4, sort_keys=True)
        return group_path

    def save_article(self, article, group_path):
        filename = os.path.join(group_path, article['name'] + ContentRepository.CONTENT_EXTENSION)
        with open(filename, 'w') as file:
            LOG.info('saving article content {} to path {}', article['name'], filename)
            file_content = html2text.html2text(article['body'])
            file.write(file_content)
        return filename

    def get_translated_group(self, files):
        result = {}
        master_name, master_ext = os.path.splitext(ContentRepository.CONTENT_FILENAME)
        for file in files:
            if file == ContentRepository.CONTENT_FILENAME:
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
        article_names = filter(lambda a: a.endswith(ContentRepository.CONTENT_EXTENSION), files)
        article_names_bits = map(lambda a: a.split('.'), article_names)
        article_names_bits = filter(lambda a: len(a) == 2, article_names_bits)
        article_names = map(lambda a: a[0], article_names_bits)

        for article_name in article_names:
            translated_articles = {}
            articles = [article for article in files if
                        article.startswith(article_name) and article.endswith(ContentRepository.CONTENT_EXTENSION)]
            for article in articles:
                if article == article_name + ContentRepository.CONTENT_EXTENSION:
                    translated_articles['en-us'] = article
                else:
                    name, ext = os.path.splitext(article)
                    if name.startswith(article_name + '.') and ext == ContentRepository.CONTENT_EXTENSION:
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
        print(url)
        print(response.status_code)
        return response.status_code == 200

    def delete_section(self, section_id):
        url = self.url_for('sections/{}.json'.format(section_id))
        LOG.debug('deleting section from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        print(url)
        print(response.status_code)
        return response.status_code == 200

    def delete_category(self, category_id):
        url = self.url_for('categories/{}.json'.format(category_id))
        LOG.debug('deleting category from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        print(url)
        print(response.status_code)
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
            print(self.url_for('files'))
            print(response.status_code)


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
        categories = self.zendesk.fetch_categories()
        for category in categories:
            LOG.debug('creating category {}', category['name'])
            category_path = self.repository.save_group(category, self.options['root_folder'])
            self.meta.save_group(category, category_path)
            self.create_sections(category['id'], category_path)

    def create_sections(self, category_id, category_path):
        sections = self.zendesk.fetch_sections(category_id)
        for section in sections:
            LOG.debug('creating section {}', section['name'])
            section_path = self.repository.save_group(section, category_path)
            self.meta.save_group(section, section_path)
            self.create_articles(section['id'], section_path)

    def create_articles(self, section_id, section_path):
        articles = self.zendesk.fetch_articles(section_id)
        for article in articles:
            LOG.debug('creating article {}', article['name'])
            self.repository.save_article(article, section_path)
            self.meta.save_article(article, section_path)


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

    def is_file_to_translate(self, path):
        _, ext = os.path.splitext(path)
        name = os.path.basename(path)
        return ext in TranslateTask.TRANSLATE_EXTENSIONS or self.repo.is_content(name)

    def execute(self):
        LOG.info('executing translate task...')
        for root, _, files in os.walk(self.options['root_folder']):
            files = filter(self.is_file_to_translate, files)
            for file in files:
                filepath = os.path.join(root, file)
                LOG.info('uploading {}', filepath)
                self.translate.create_file(filepath)


class RemoveTask(object):

    """
    Removes articles, sections and categories.
    """

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options)
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
        self.repo.delete_group(path)

    def _delete_article(self, path):
        article_name, _ = os.path.splitext(os.path.basename(path))
        article_dir = os.path.dirname(path)
        article_id = self.meta.article_id(article_dir, article_name)
        LOG.info('deleting article {} from {}', article_name, path)
        self.zendesk.delete_article(article_id)
        self.meta.delete_article(article_dir, article_name)
        self.repo.delete_article(article_dir, article_name)


tasks = {
    'import': ImportTask,
    'export': ExportTask,
    'translate': TranslateTask,
    'remove': RemoveTask
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('task',
                        help='Task to be performed.',
                        choices=tasks.keys())
    parser.add_argument('-v', '--verbose', help='Increase output verbosity',
                        action='store_true')
    parser.add_argument('-p', '--path', help='Set path for the remove task')
    parser.add_argument('-r', '--root',
                        help='Article\'s root folder',
                        default='help_center_content')
    return parser.parse_args()


def parse_options():
    config = configparser.ConfigParser()
    config.read('translator.cfg')

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

    options['path'] = args.path
    options['root'] = args.root

    return task, options


def main():
    args = parse_args()
    options = parse_options()
    task, options = resolve_args(args, options)
    task.execute()


if __name__ == '__main__':
    main()
