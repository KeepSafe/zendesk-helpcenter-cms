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
import requests
import unicodedata


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
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
    META_FILENAME = 'meta.json'

    def save_group(self, group, path):
        file_content = {
            'name': group['name'],
            'description': group['description']
        }
        with open(os.path.join(path, MetaRepository.META_FILENAME), 'w') as file:
            json.dump(file_content, file, indent=4, sort_keys=True)

    def save_article(self, article, path):
        with open(os.path.join(path, slugify(article['name']) + '.json'), 'w') as file:
            json.dump(article, file, indent=4, sort_keys=True)


class ArticleRepository(object):
    def save_group(self, group, path):
        group_path = os.path.join(path, group['name'])
        os.makedirs(group_path, exist_ok=True)
        return group_path

    def save_article(self, article, group_path):
        file_content = html2text.html2text(article['body'])
        with open(os.path.join(group_path, slugify(article['name']) + '.md'), 'w') as file:
            file.write(file_content)


class ZendeskClient(object):
    DEFAULT_URL = 'https://{}.zendesk.com/hc/api/v2/{}'

    def __init__(self, company_name):
        super().__init__()
        self.company_name = company_name

    def url_for(self, path):
        return ZendeskClient.DEFAULT_URL.format(self.company_name, path)

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


class ImportTask(object):
    def __init__(self, options):
        super().__init__()
        self.options = options
        self.zendesk = ZendeskClient(options['company_name'])
        self.repository = ArticleRepository()
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

    def execute(self):
        print('export task')


class TranslateTask(object):
    def __init__(self, options):
        super().__init__()

    def execute(self):
        print('translate task')


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
        'company_name': 'testingzendesk12',
        'root_folder': 'help_center_content'
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
