"""
    translator
    ~~~~~~~~~~

    Manages zendesk help center translations.

    :copyright: (c) 2014 by KeepSafe.
"""
import argparse
import os
import configparser

import logging
import services
import items
import exceptions

DEFAULE_LOG_LEVEL = 'WARNING'
CONFIG_FILE = 'translator.config'
ZENDESK_REQUIRED_CONFIG = ['company_name', 'user', 'password']
WEBTRANSLATEIT_REQUIRED_CONFIG = ['webtranslateit_api_key']


class AbstractTask(object):

    def __init__(self, options=None):
        super().__init__()
        self.options = options or {}

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
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG)

    def execute(self):
        logging.info('executing import task...')
        self.create_categories()

    def create_categories(self):
        zendesk_categories = services.zendesk.fetch_categories()
        for zendesk_category in zendesk_categories:
            logging.debug('creating category %s', zendesk_category['name'])
            category = items.Group.from_zendesk(self.options['root_folder'], zendesk_category)
            self.create_sections(category)

    def create_sections(self, category):
        zendesk_sections = services.zendesk.fetch_sections(category.zendesk_id)
        for zendesk_section in zendesk_sections:
            logging.debug('creating section %s', zendesk_section['name'])
            section = items.Group.from_zendesk(category.path, zendesk_section, category)
            self.create_articles(section)

    def create_articles(self, section):
        zendesk_articles = services.zendesk.fetch_articles(section.zendesk_id)
        for zendesk_article in zendesk_articles:
            logging.debug('creating article %s', zendesk_article['name'])
            items.Article.from_zendesk(section.path, zendesk_article)


class ExportTask(AbstractTask):

    """
    Exports content to Zendesk. It will update everything, creating whats missing along the way. Every time this task
    is used the ENTIRE content is uploaded.
    """

    def __init__(self, options):
        super().__init__(options)
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG)

    def execute(self):
        logging.info('executing export task...')
        root = self.options['root_folder']
        category_paths = [os.path.join(root, name) for name in os.listdir(root)
                          if not os.path.isfile(os.path.join(root, name))]
        for category_path in category_paths:
            category = items.Group(category_path)
            category_id = category.zendesk_id
            if category_id:
                logging.info('exporting category from %s', category.content_filename)
                services.zendesk.update_category(category)
            else:
                logging.info('exporting new category from %s', category.content_filename)
                new_category = services.zendesk.create_category(category.translations)
                category.meta = new_category
                category_id = new_category['id']
            sections = category.children
            for section in sections:
                section_id = section.zendesk_id
                if section_id:
                    logging.info('exporting section from %s', section.content_filename)
                    services.zendesk.update_section(section)
                else:
                    logging.info('exporting new section from %s', section.content_filename)
                    new_section = services.zendesk.create_section(category_id, section.translations)
                    section.meta = new_section
                    section_id = new_section['id']
                articles = section.children
                for article in articles:
                    article_id = article.zendesk_id
                    if article_id:
                        logging.info('exporting article %s from %s', article.name, article.path)
                        services.zendesk.update_article(article, self.options['image_cdn'])
                    else:
                        logging.info('exporting new article %s from %s', article.name, article.path)
                        new_article = services.zendesk.create_article(
                            section_id,
                            self.options['image_cdn'],
                            self.options['disable_article_comments'],
                            article.translations)
                        article.meta = new_article


class TranslateTask(AbstractTask):

    """
    Upload content to WebTranslateIt. Should only be used to upload the initial conent in the default language after
    it has been imported from Zendesk.
    """

    def __init__(self, options):
        super().__init__(options)
        self._validate_options(options, WEBTRANSLATEIT_REQUIRED_CONFIG)

    def execute(self):
        logging.info('executing translate task...')
        root = self.options['root_folder']
        for filepath in os.listdir(root):
            category_path = os.path.join(root, filepath)
            if os.path.isdir(category_path):
                category = items.Group(category_path)
                logging.info('upload %s for transaltion', category.content_filename)
                category_translate_id = services.translate.create(category.content_filename)
                if category_translate_id:
                    category_meta = category.meta
                    category_meta.update({'webtranslateit_ids': [category_translate_id]})
                    category.meta = category_meta
                for section in category.children:
                    logging.info('upload %s for transaltion', section.content_filename)
                    section_translate_id = services.translate.create(section.content_filename)
                    if section_translate_id:
                        section_meta = section.meta
                        section_meta.update({'webtranslateit_ids': [section_translate_id]})
                        section.meta = section_meta
                    for article in section.children:
                        logging.info('upload %s for transaltion', article.content_filename)
                        content_translate_id = services.translate.create(article.content_filename)
                        logging.info('upload %s for transaltion', article.body_filename)
                        body_translate_id = services.translate.create(article.body_filename)
                        if content_translate_id or body_translate_id:
                            article_meta = article.meta
                            article_meta.update({'webtranslateit_ids': [body_translate_id, content_translate_id]})
                            article.meta = article_meta


class RemoveTask(AbstractTask):

    """
    Removes articles, sections and categories.
    """

    def __init__(self, options):
        super().__init__(options)
        self._validate_options(options, ZENDESK_REQUIRED_CONFIG + WEBTRANSLATEIT_REQUIRED_CONFIG)

    def execute(self):
        logging.info('executing delete task...')
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
        logging.info('deleting group from %s', path)
        category, section = items.Group.from_path(self.options['root'], path)
        if section:
            group = section
            for article in group.children:
                self._delete_article(article)
        else:
            group = category
            for section in group.children:
                self._delete_group(section.path)
        services.zendesk.delete_section(group.zendesk_id)
        services.translate.delete(group.translate_ids)
        group.remove()

    def _delete_article(self, article):
        logging.info('deleting article %s from %s', article.name, article.path)
        article_id = article.zendesk_id
        if article_id:
            services.zendesk.delete_article(article.zendesk_id)
        services.translate.delete(article.translate_ids)
        article.remove()


class MoveTask(AbstractTask):

    """
    Move article to a different section/category
    """

    def __init__(self, options):
        super().__init__(options)
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
            logging.info('moving article %s to section %s', article.name, dest_section.path)
            body_translate_id, content_translate_id = article.translate_ids
            services.zendesk.move_article(article.zendesk_id, dest_section.zendesk_id)
            article.move_to(dest_section)
            services.translate.move(body_translate_id, article.body_filename)
            services.translate.move(content_translate_id, article.content_filename)
        elif group:
            logging.info('moving section %s to category %s', group.path, dest_category.path)
            content_translate_id, = group.translate_ids
            services.zendesk.move_section(group.zendesk_id, dest_category.zendesk_id)
            group.move_to(dest_category)
            for article in group.children:
                logging.info('moving article %s in translations', article.name)
                body_translate_id, content_translate_id = article.translate_ids
                services.translate.move(body_translate_id, article.body_filename)
                services.translate.move(content_translate_id, article.content_filename)
            services.translate.move(content_translate_id, group.content_filename)

        else:
            raise ValueError('Neither section nor article was specified as source. please check the path {}'
                             .format(source))


class DoctorTask(AbstractTask):

    """
    Verifies if everything is valid and creates missing files.
    """

    def execute(self):
        logging.info('executing doctor task...')
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
            default_image_cdn = default_config.get('image_cdn', '')
            image_cdn = input('CDN path for storing images ({}):'.format(default_image_cdn)) or default_image_cdn
            default_disable_article_comments = default_config.get('disable_article_comments', '')
            disable_article_comments = input('Disable article comments ({}):'.format(default_disable_article_comments))
            disable_article_comments = disable_article_comments or default_disable_article_comments
        else:
            company_name = input('Zendesk\'s company name:')
            user = input('Zendesk\'s user name:')
            password = input('Zendesk\'s password:')
            webtranslateit_api_key = input('WebTranslateIt private API key:')
            image_cdn = input('CDN path for storing images:')
            disable_article_comments = input('Disable article comments:')

        return {
            'company_name': company_name,
            'user': user,
            'password': password,
            'webtranslateit_api_key': webtranslateit_api_key,
            'image_cdn': image_cdn,
            'disable_article_comments': disable_article_comments
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
    parser.add_argument('-l', '--loglevel',
                        help='Specify log level (DEBUG, INFO, WARNING, ERROR, CRITICAL), default: %s'
                        % DEFAULE_LOG_LEVEL,
                        default=DEFAULE_LOG_LEVEL)
    parser.add_argument('-r', '--root_folder',
                        help='items.Article\'s root folder',
                        default=os.getcwd())

    # Task subparser settings
    task_parsers['remove'].add_argument('path', help='Set path for removing an item')
    task_parsers['move'].add_argument('source', help='Set source section/article')
    task_parsers['move'].add_argument('destination', help='Set destination category/section')

    return parser.parse_args()


def init_log(loglevel):
    num_level = getattr(logging, loglevel.upper(), 'WARNING')
    logging.basicConfig(level=num_level)


def parse_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return dict(config[config.default_section])


def resolve_args(args, options):
    task = tasks[args.task](options)

    for key, value in vars(args).items():
        options[key] = value

    return task, options


def fix_defaults(options):
    options['image_cdn'] = options.get('image_cdn', '')
    options['disable_article_comments'] = bool(options.get('disable_article_comments', False))
    return options


def main():
    args = parse_args()
    init_log(args.loglevel)
    options = parse_config()
    fix_defaults(options)
    task, options = resolve_args(args, options)
    services.zendesk.req = services.ZendeskRequest(options['company_name'], options['user'], options['password'])
    services.translate.api_key = options['webtranslateit_api_key']

    task.execute()


if __name__ == '__main__':
    main()
