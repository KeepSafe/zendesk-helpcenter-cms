"""
    translator
    ~~~~~~~~~~

    Manages zendesk help center translation.

    :copyright: (c) 2014 by KeepSafe.
"""
import argparse


class ImportTask(object):
    def __init__(self, options):
        super().__init__()

    def execute(self):
        print('import task')


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


def resolve_args(args):
    options = {}
    task = tasks[args.task](options)

    return task, options


def main():
    args = parse_args()
    task, options = resolve_args(args)
    task.execute()


if __name__ == '__main__':
    main()
