"""
    translator
    ~~~~~~~~~~

    Manages zendesk help center translations.

    :copyright: (c) 2014 by KeepSafe.
"""
import argparse
import os
import configparser

import utils
import services
import items
import exceptions

LOG = utils.Logger()
CONFIG_FILE = 'translator.config'
ZENDESK_REQUIRED_CONFIG = ['company_name', 'user', 'password']
WEBTRANSLATEIT_REQUIRED_CONFIG = ['webtranslateit_api_key']


class AbstractTask(object):

    def __init__(self, options=None):
        super().__init__()
        self.options = options or {}
        self.options['root_folder'] = os.getcwd()

    def _validate_options(self, options, required_params=None):
        missing_property_msg = 'there is no "{}" defined in the configuration. please check the docs for help'
        required_params = required_params or []

        for param in required_params:
            if param not in options:
                raise exceptions.ConfigError(missing_property_msg.format(param))


class ImportTask(AbstractTask):

    """
    Imports an existing content from Zendesk. This should only be used to initialize the project. Later on edits
    should be done directly on the files.
    """

    def __init__(self, options):
        super().__init__(options)
        self.zendesk = services.ZendeskService(options)
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG)

    def execute(self):
        LOG.info('executing import task...')
        self.create_categories()

    def create_categories(self):
        zendesk_categories = self.zendesk.fetch_categories()
        for zendesk_category in zendesk_categories:
            LOG.debug('creating category {}', zendesk_category['name'])
            category = items.Group.from_zendesk(self.options['root_folder'], zendesk_category)
            self.create_sections(category)

    def create_sections(self, category):
        zendesk_sections = self.zendesk.fetch_sections(category.zendesk_id)
        for zendesk_section in zendesk_sections:
            LOG.debug('creating section {}', zendesk_section['name'])
            section = items.Group.from_zendesk(category.path, zendesk_section, category)
            self.create_articles(section)

    def create_articles(self, section):
        zendesk_articles = self.zendesk.fetch_articles(section.zendesk_id)
        for zendesk_article in zendesk_articles:
            LOG.debug('creating article {}', zendesk_article['name'])
            items.Article.from_zendesk(section.path, zendesk_article)


class ExportTask(AbstractTask):

    """
    Exports content to Zendesk. It will update everything, creating whats missing along the way. Every time this task
    is used the ENTIRE content is uploaded.
    """

    def __init__(self, options):
        super().__init__(options)
        self.zendesk = services.ZendeskService(options)
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG)

    def execute(self):
        LOG.info('executing export task...')
        root = self.options['root_folder']
        category_paths = [os.path.join(root, name) for name in os.listdir(root)
                          if not os.path.isfile(os.path.join(root, name))]
        for category_path in category_paths:
            category = items.Group(category_path)
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
                        self.zendesk.update_article(article, self.options['image_cdn'])
                    else:
                        LOG.info('exporting new article {} from {}', article.name, article.path)
                        new_article = self.zendesk.create_article(
                            section_id, self.options['image_cdn'], article.translations)
                        article.meta = new_article


class TranslateTask(AbstractTask):

    """
    Upload content to WebTranslateIt. Should only be used to upload the initial conent in the default language after
    it has been imported from Zendesk.
    """

    def __init__(self, options):
        super().__init__(options)
        self.translate = services.WebTranslateItService(options)
        self._validate_options(options, WEBTRANSLATEIT_REQUIRED_CONFIG)

    def execute(self):
        LOG.info('executing translate task...')
        root = self.options['root_folder']
        for filepath in os.listdir(root):
            category_path = os.path.join(root, filepath)
            if os.path.isdir(category_path):
                category = items.Group(category_path)
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


class RemoveTask(AbstractTask):

    """
    Removes articles, sections and categories.
    """

    def __init__(self, options):
        super().__init__(options)
        self.zendesk = services.ZendeskService(options)
        self.translate = services.WebTranslateItService(options)
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG + WEBTRANSLATEIT_REQUIRED_CONFIG)

    def execute(self):
        LOG.info('executing delete task...')
        path = self.options['path']
        if not os.path.exists(path):
            raise ValueError('Path to be deleted must exists, but {} doesn\'t'.format(path))

        if os.path.isfile(path):
            article_name, _ = os.path.splitext(os.path.basename(path))
            article_dir = os.path.dirname(path)
            self._delete_article(items.Article(article_dir, article_name))
        else:
            self._delete_group(path)

    def _delete_group(self, path):
        LOG.info('deleting group from {}', path)
        category, section = items.Group.from_path(self.options['root'], path)
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


class MoveTask(AbstractTask):

    """
    Move article to a different section/category
    """

    def __init__(self, options):
        super().__init__(options)
        self.zendesk = services.ZendeskService(options)
        self.translate = services.WebTranslateItService(options)
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG + WEBTRANSLATEIT_REQUIRED_CONFIG)

    def execute(self):
        source = self.options['source']
        destination = self.options['destination']
        article = None
        group = None

        if os.path.isfile(source):
            article_name, _ = os.path.splitext(os.path.basename(source))
            article_dir = os.path.dirname(source)
            article = items.Article(article_dir, article_name)
        else:
            category = items.Group(os.path.dirname(source))
            group = items.Group(source, category)

        dest_category, dest_section = items.Group.from_path(self.options['root'], destination)

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


class DoctorTask(AbstractTask):

    """
    Verifies if everything is valid and creates missing files.
    """

    def execute(self):
        LOG.info('executing doctor task...')
        root = self.options['root_folder']
        category_paths = [os.path.join(root, name) for name in os.listdir(root)
                          if not os.path.isfile(os.path.join(root, name))]
        for category_path in category_paths:
            category = items.Group(category_path)
            category.fixme()
            for section in category.children:
                section.fixme()
                for article in section.children:
                    article.fixme()


class ConfigTask(AbstractTask):

    """
    Creates cofig file in the current directory by asking a user to provide the data.
    """

    def _read_existing_config(self):
        if not os.path.exists(CONFIG_FILE):
            return {}

        print('There is a config alread present, press ENTER to accept already existing value')
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        return dict(config[config.default_section])

    def _read_config_from_input(self, default_config):
        if default_config:
            default_company_name = default_config.get('company_name', '')
            company_name = input('Zendesk\'s company name ({}):'.format(default_company_name)) or default_company_name
            default_user = default_config.get('user', '')
            user = input('Zendesk\'s user name ({}):'.format(default_user)) or default_user
            default_password = default_config.get('password', '')
            password = input('Zendesk\'s password ({}):'.format(default_password)) or default_password
            default_api_key = default_config.get('webtranslateit_api_key', '')
            webtranslateit_api_key = input(
                'WebTranslateIt private API key ({}):'.format(default_api_key)) or default_api_key
            default_image_cdn = default_config.get('webtranslateit_api_key', '')
            image_cdn = input('CDN path for storing images ({}):'.format(default_image_cdn)) or default_image_cdn
        else:
            company_name = input('Zendesk\'s company name:')
            user = input('Zendesk\'s user name:')
            password = input('Zendesk\'s password:')
            webtranslateit_api_key = input('WebTranslateIt private API key:')
            image_cdn = input('CDN path for storing images:')

        return {
            'company_name': company_name,
            'user': user,
            'password': password,
            'webtranslateit_api_key': webtranslateit_api_key,
            'image_cdn': image_cdn
        }

    def execute(self):
        existing_config = self._read_existing_config()
        user_config = self._read_config_from_input(existing_config)

        config = configparser.ConfigParser()
        config[config.default_section] = user_config

        with open(CONFIG_FILE, 'w') as config_file:
            config.write(config_file)


tasks = {
    'import': ImportTask,
    'export': ExportTask,
    'translate': TranslateTask,
    'remove': RemoveTask,
    'move': MoveTask,
    'doctor': DoctorTask,
    'config': ConfigTask
}


def parse_args():
    parser = argparse.ArgumentParser()

    # Subparsers
    subparsers = parser.add_subparsers(help='Task to be performed.', dest='task')
    task_parsers = {task_parser: subparsers.add_parser(task_parser) for task_parser in tasks}

    # Global settings
    parser.add_argument('-v', '--verbose', help='Increase output verbosity',
                        action='store_true')
    parser.add_argument('-r', '--root',
                        help='items.Article\'s root folder',
                        default='help_center_content')

    # Task subparser settings
    task_parsers['remove'].add_argument('path', help='Set path for removing an item')
    task_parsers['move'].add_argument('source', help='Set source section/article')
    task_parsers['move'].add_argument('destination', help='Set destination category/section')

    return parser.parse_args()


def parse_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return dict(config[config.default_section])


def resolve_args(args, options):
    task = tasks[args.task](options)
    LOG.verbose = args.verbose

    for key, value in vars(args).items():
        options[key] = value

    return task, options


def main():
    args = parse_args()
    options = parse_config()
    task, options = resolve_args(args, options)
    task.execute()


if __name__ == '__main__':
    main()
