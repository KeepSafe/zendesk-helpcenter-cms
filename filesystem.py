import json
import os
import logging
import re
import shutil

import model
import utils

GROUP_TRANSLATION_PATTERN = '{}.([a-zA-Z-]{{2,5}}){}'


class FilesystemClient(object):

    def __init__(self, root_folder):
        self.root_folder = root_folder

    def _path_for(self, path):
        return os.path.join(self.root_folder, path)

    def save_text(self, path, data):
        full_path = self._path_for(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as fp:
            fp.write(data)

    def read_text(self, path):
        full_path = self._path_for(path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as fp:
                return fp.read()
        else:
            return ''

    def save_json(self, path, data):
        text = json.dumps(data, indent=4, sort_keys=True)
        self.save_text(path, text)

    def read_json(self, path):
        text = self.read_text(path)
        if text:
            return json.loads(text)
        else:
            return {}

    def read_directories(self, path):
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)) and not d.startswith('.')]

    def read_files(self, path):
        return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

    def remove(self, filepath):
        os.remove(filepath)

    def remove_dir(self, path):
        shutil.rmtree(path)

    def move(self, old_path, new_path):
        if os.path.exists(old_path):
            shutil.move(old_path, new_path)


class Saver(object):

    def __init__(self, fs):
        self.fs = fs

    def _save_item(self, item):
        self.fs.save_json(item.meta_filepath, item.meta)
        self.fs.save_json(item.content_filepath, item.to_content())

    def save(self, categories):
        for category in categories:
            self._save_item(category)
            logging.info('Category %s saved' % category.name)
            for section in category.sections:
                self._save_item(section)
                logging.info('Section %s saved' % section.name)
                for article in section.articles:
                    self._save_item(article)
                    logging.info('Article %s saved' % article.name)
                    self.fs.save_text(article.body_filepath, article.body)


class Loader(object):

    def __init__(self, fs):
        self.fs = fs

    def _slugify_name(self, dir_path, name, ext=''):
        slugify_name = utils.slugify(name)
        if name.startswith('.'):
            slugify_name = '.' + slugify_name
        if name != slugify_name:
            old_path = os.path.join(dir_path, name + ext)
            new_path = os.path.join(dir_path, slugify_name + ext)
            self.fs.move(old_path, new_path)
        return slugify_name + ext

    def _slugify_category(self, category_path):
        category_name = self._slugify_name(os.path.dirname(category_path), os.path.basename(category_path))
        return os.path.join(os.path.dirname(category_path), category_name)

    def _slugify_section(self, category_path, section_name):
        return self._slugify_name(category_path, section_name)

    def _slugify_article(self, article_path):
        article_name, article_ext = os.path.splitext(os.path.basename(article_path))
        article_dir = os.path.dirname(article_path)
        slugify_article_name = self._slugify_name(article_dir, article_name, article_ext)
        return os.path.join(article_dir, slugify_article_name)

    def _load_category(self, category_path):
        category_path = self._slugify_category(category_path)
        category_name = os.path.basename(category_path)
        meta_path, content_path = model.Category.filepaths_from_path(category_path)
        meta = self.fs.read_json(meta_path)
        content = self.fs.read_json(content_path)
        content = content or {'name': os.path.basename(category_path)}
        return model.Category.from_dict(meta, content, category_name)

    def _load_section(self, category, section_name):
        slugify_section_name = self._slugify_section(category.path, section_name)
        meta_path, content_path = model.Section.filepaths_from_path(category, slugify_section_name)
        meta = self.fs.read_json(meta_path)
        content = self.fs.read_json(content_path)
        content = content or {'name': section_name}
        return model.Section.from_dict(category, meta, content, slugify_section_name)

    def _load_article(self, section, article_name):
        meta_path, content_path, body_path = model.Article.filepaths_from_path(section, article_name)
        meta_path = self._slugify_article(meta_path)
        content_path = self._slugify_article(content_path)
        body_path = self._slugify_article(body_path)
        meta = self.fs.read_json(meta_path)
        content = self.fs.read_json(content_path)
        content = content or {'name': article_name}
        body = self.fs.read_text(body_path)
        return model.Article.from_dict(section, meta, content, body, utils.slugify(article_name))

    def _filter_article_names(self, files):
        articles = [a for a in files if a.endswith(model.Article._body_exp)]
        return map(lambda a: os.path.splitext(a)[0], articles)

    def _group_locales(self, group):
        pattern = GROUP_TRANSLATION_PATTERN.format(group.content_filename, group._content_exp)
        locales = []
        for filename in self.fs.read_files(group.path):
            match = re.match(pattern, filename)
            if match:
                locales.append(match.group(1))
        locales.append('')  # HACK use as default locale
        return locales

    def _article_locales(self, article):
        locales = []
        for name in self.fs.read_directories(article.section.path):
            locales.append(name)
        return locales

    def _group_translations(self, group):
        translations = []
        locales = self._group_locales(group)
        for locale in locales:
            content_path = group.content_translation_filepath(locale)
            content = self.fs.read_json(content_path)
            if 'name' in content:
                translations.append(model.GroupTranslation(locale, content['name'], content['description']))
            else:
                print('Missing content from {}. Skipping translation'.format(content_path))
        return translations

    def _article_translations(self, article):
        translations = []
        locales = self._article_locales(article)
        for locale in locales:
            content_path = article.content_translation_filepath(locale)
            body_path = article.body_translation_filepath(locale)
            content = self.fs.read_json(content_path)
            body = self.fs.read_text(body_path)
            if 'name' in content:
                translations.append(model.ArticleTranslation(locale, content['name'], body))
            else:
                print('Missing content from {}. Skipping translation'.format(content_path))
        return translations

    def _fill_category(self, category_name):
        category = self._load_category(os.path.join(self.fs.root_folder, category_name))
        category.translations = self._group_translations(category)
        self._fill_sections(category)
        return category

    def _fill_sections(self, category):
        for section_name in self.fs.read_directories(category.path):
            section = self._load_section(category, section_name)
            section.translations = self._group_translations(section)
            category.sections.append(section)
            self._fill_articles(section)

    def _fill_articles(self, section):
        articles_path = model.Article.path_from_section(section)
        os.makedirs(articles_path, exist_ok=True)
        article_names = self._filter_article_names(self.fs.read_files(articles_path))
        for article_name in article_names:
            article = self._load_article(section, article_name)
            article.translations = self._article_translations(article)
            section.articles.append(article)

    def load(self):
        categories = []
        for category_name in self.fs.read_directories(self.fs.root_folder):
            category = self._fill_category(category_name)
            categories.append(category)
        return categories

    def load_from_path(self, path):
        if os.path.isfile(path):
            article_name, = os.path.splitext(path)
            section_path = os.path.dirname(os.path.dirname(path))
            section_name = os.path.basename(section_path)
            category_path = os.path.dirname(section_path)
            category = self._load_category(category_path)
            section = self._load_section(category, section_name)
            article = self._load_article(section, article_name)
            article.translations = self._article_translations(article)
            return article
        elif os.path.samefile(os.path.dirname(path), self.fs.root_folder):
            return self._fill_category(os.path.basename(path))
        else:
            section_name = os.path.basename(path)
            category_path = os.path.dirname(path)
            category = self._load_category(category_path)
            section = self._load_section(category, section_name)
            self._fill_articles(section)
            return section


class Remover(object):

    def __init__(self, fs):
        self.fs = fs

    def _remove_article(self, article):
        for translation in article.translations:
            self.fs.remove(article.content_translation_filepath(translation.locale))
            self.fs.remove(article.body_translation_filepath(translation.locale))
        self.fs.remove(article.meta_filepath)
        self.fs.remove(article.content_filepath)
        self.fs.remove(article.body_filepath)

    def _remove_group(self, section):
        self.fs.remove_dir(section.path)

    def remove(self, item):
        # TODO to be improved, read above
        if isinstance(item, model.Article):
            self._remove_article(item)
        if isinstance(item, model.Section):
            self._remove_group(item)
        if isinstance(item, model.Category):
            self._remove_group(item)


class Doctor(object):

    def __init__(self, fs):
        self.fs = fs

    def _fix_item_content(self, item):
        if not os.path.exists(item.content_filepath):
            print('Missing content file {} created'.format(item.content_filepath))
            content = item.to_content()
            for key, value in content.items():
                new_value = input('Please provide a {} for this item (default: {})'.format(key, value))
                new_value = new_value or value
                content[key] = new_value
            self.fs.save_json(item.content_filepath, content)
        # else:
        #     content = self.fs.read_json(item.content_filepath)
        #     if 'name' not in content:
        #         print('Content {} is invalid'.format(item.content_filepath))
        #         item_content = item.to_content()
        #         for key, value in item_content.items():
        #             new_value = input('Please provide a {} for this item (default: {})'.format(key, value))
        #             new_value = new_value or value
        #             item_content[key] = new_value
        #         self.fs.save_json(item.content_filepath, item_content)

    def fix_category(self, category):
        self._fix_item_content(category)

    def fix_section(self, section):
        self._fix_item_content(section)

    def fix_article(self, article):
        self._fix_item_content(article)


def saver(root_folder):
    fs = FilesystemClient(root_folder)
    return Saver(fs)


def loader(root_folder):
    fs = FilesystemClient(root_folder)
    return Loader(fs)


def remover(root_folder):
    fs = FilesystemClient(root_folder)
    return Remover(fs)


def doctor(root_folder):
    fs = FilesystemClient(root_folder)
    return Doctor(fs)


def client(root_folder):
    return FilesystemClient(root_folder)
