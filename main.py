import argparse
import os
import logging
import configparser

import zendesk
import filesystem
import translate

DEFAULE_LOG_LEVEL = 'WARNING'
CONFIG_FILE = 'translator.config'


class ImportTask(object):

    def execute(self, args):
        print('Running import task...')
        categories = zendesk.fetcher(args['company_name'], args['user'], args['password']).fetch()
        filesystem.saver(args['root_folder']).save(categories)
        print('Done')


class TranslateTask(object):

    def execute(self, args):
        print('Running translate task...')
        categories = filesystem.loader(args['root_folder']).load()
        translate.translator(args['webtranslateit_api_key']).create(categories)
        print('Done')


class ExportTask(object):

    def execute(self, args):
        DoctorTask().execute(args)
        print('Running translate task...')
        categories = filesystem.loader(args['root_folder']).load()
        filesystem_client = filesystem.client(args['root_folder'])
        zendesk.pusher(args['company_name'], args['user'], args['password'],
                       filesystem_client, args['image_cdn']).push(categories)
        print('Done')


class RemoveTask(object):

    def execute(self, args):
        print('Running remove task...')
        path = os.path.join(args['root_folder'], args['path'])

        if not os.path.exists(path):
            logging.error('Provided path %s does not exist', path)
            return

        item = filesystem.loader(args['root_folder']).load_from_path(path)
        zendesk.remover(args['company_name'], args['user'], args['password']).remove(item)
        translate.remover(args['webtranslateit_api_key']).remove(item)
        filesystem.remover(args['root_folder']).remove(item)
        print('Done')


class MoveTask(object):

    def execute(self, args):
        print('Running move task...')
        src = os.path.join(args['root_folder'], args['source'])
        dest = os.path.join(args['root_folder'], args['destination'])

        if not os.path.exists(src):
            logging.error('Provided source %s does not exist', src)
            return
        if os.path.exists(dest):
            logging.error('Provided destination %s already exist', dest)
            return

        item = filesystem.loader(args['root_folder']).load_from_path(src)
        zendesk.mover(args['company_name'], args['user'], args['password'], args['image_cdn']).move(item, dest)
        translate.mover(args['webtranslateit_api_key']).move(item, dest)
        filesystem.mover(args['root_folder']).move(item, dest)
        print('Done')


class DoctorTask(object):

    def execute(self, args):
        print('Running doctor task...')
        categories = filesystem.loader(args['root_folder']).load()
        filesystem_client = filesystem.client(args['root_folder'])
        filesystem_doctor = filesystem.doctor(args['root_folder'])
        translate_doctor = translate.doctor(args['webtranslateit_api_key'])
        zendesk_doctor = zendesk.doctor(args['company_name'], args['user'], args['password'], filesystem_client)

        for category in categories:
            print('Validating category {}'.format(category.name))
            zendesk_doctor.fix_category(category)
            filesystem_doctor.fix_category(category)
            translate_doctor.fix_category(category)
            for section in category.sections:
                print('Validating section {}'.format(section.name))
                zendesk_doctor.fix_section(section)
                filesystem_doctor.fix_section(section)
                translate_doctor.fix_section(section)
                for article in section.articles:
                    print('Validating article {}'.format(article.name))
                    zendesk_doctor.fix_article(article)
                    filesystem_doctor.fix_article(article)
                    translate_doctor.fix_article(article)

        print('Done')

tasks = {
    'import': ImportTask(),
    'translate': TranslateTask(),
    'export': ExportTask(),
    'remove': RemoveTask(),
    'move': MoveTask(),
    'doctor': DoctorTask()
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
    task_parsers['remove'].add_argument('path',
                                        help='Set path for removing an item. The path is relative to the root folder')
    task_parsers['move'].add_argument('source', help='Set source section/article')
    task_parsers['move'].add_argument('destination', help='Set destination category/section')

    return parser.parse_args()


def init_log(loglevel):
    num_level = getattr(logging, loglevel.upper(), 'WARNING')
    logging.basicConfig(level=num_level)


def parse_config(args):
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    options = dict(config[config.default_section])
    options.update(vars(args))
    options['image_cdn'] = options.get('image_cdn', '')
    options['disable_article_comments'] = bool(options.get('disable_article_comments', False))
    return options


def main():
    args = parse_args()
    init_log(args.loglevel)
    options = parse_config(args)
    task = tasks[options['task']]
    task.execute(options)


if __name__ == '__main__':
    main()