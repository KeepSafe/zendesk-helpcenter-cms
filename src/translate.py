import os
import requests
import logging

import model


class WebTranslateItRequest(object):
    _default_url = 'https://webtranslateit.com/api/projects/{}/{}'
    _project_url = 'https://webtranslateit.com/api/projects/{}.json'
    _file_url = 'https://webtranslateit.com/api/projects/{}/files/...?file_path={}'

    def __init__(self, api_key):
        self.api_key = api_key

    def _url_for(self, path):
        return self._default_url.format(self.api_key, path)

    def _path_url_for(self, path):
        return self._file_url.format(self.api_key, path)

    def get_master_files(self):
        url = self._project_url.format(self.api_key)
        res = requests.get(url)
        files = res.json()['project']['project_files']
        return list(filter(lambda f: f['locale_code'] == model.DEFAULT_LOCALE, files))

    def _send_request(self, request_fn, url, data, files):
        full_url = self._url_for(url)
        response = request_fn(full_url, data=data, files=files)
        return self._parse_response(response)

    def _parse_response(self, response):
        if response.status_code == 404:
            logging.warning('%s does not exist', response.url)
            return ''
        if response.status_code != 200:
            logging.error('getting data from %s failed. status was %s and message %s',
                          response.url, response.status_code, response.text)
            return ''

        return response.text.strip()

    def post(self, url, data, files=None):
        return self._send_request(requests.post, url, data, files)

    def put(self, url, data, files=None):
        return self._send_request(requests.put, url, data, files)

    def delete(self, url):
        full_url = self._url_for(url)
        response = requests.delete(full_url)
        return response.status_code == 200


class WebTranslateItClient(object):

    """
    Handles all reuests to WebTranslateIt
    """

    def __init__(self, req):
        self.req = req

    def _create_item(self, filepath):
        with open(filepath, 'r') as fp:
            normalized_filepath = os.path.relpath(filepath).replace('\\', '/')
            data = {'file': normalized_filepath, 'name': normalized_filepath}
            files = {'file': fp}
            return self.req.post('files', data, files)

    def _get_translate_id(self, path, master_files):
        master_files_for_item = list(filter(lambda f: f['name'] == path, master_files))
        if len(master_files_for_item) > 1:
            # TODO error?
            return ''
        elif len(master_files_for_item) == 1:
            master_file = master_files_for_item[0]
            return str(master_file['id'])

    def fix_group(self, group, master_files):
        content_path = group.content_filepath
        translate_id = self._get_translate_id(content_path, master_files)
        if translate_id and translate_id != group.translate_ids.get('content'):
            print('WebTranslateIt id is missing but found {} by path.'.format(group.name))
            group.translate_ids = {'content': translate_id}

    def fix_article(self, article, master_files):
        content_path = article.content_filepath
        content_translate_id = self._get_translate_id(content_path, master_files)
        translate_ids = article.translate_ids
        if content_translate_id and content_translate_id != article.translate_ids.get('content'):
            print('WebTranslateIt content id is missing but found {} by path.'.format(article.name))
            translate_ids['content'] = content_translate_id

        body_path = article.body_filepath
        body_translate_id = self._get_translate_id(body_path, master_files)
        if body_translate_id and body_translate_id != article.translate_ids.get('body'):
            print('WebTranslateIt body id is missing but found {} by path.'.format(article.name))
            translate_ids['body'] = body_translate_id

        if translate_ids:
            article.translate_ids = translate_ids

    def _move_item(self, file_id, filepath):
        with open(filepath, 'r') as file:
            normalized_new_path = filepath.replace('\\', '/')
            data = {'file': normalized_new_path, 'name': normalized_new_path}
            files = {'file': file}
            self.req.put('files/{}/locales/{}'.format(file_id, model.DEFAULT_LOCALE), data, files)

    def delete(self, item):
        for _, file_id in item.translate_ids.items():
            self.req.delete('files/{}'.format(file_id))

    def move(self, item, new_path):
        # Guido weeps
        if isinstance(item, model.Article):
            self._move_item(item.translate_ids['body'], item.body_filepath)
            self._move_item(item.translate_ids['content'], item.content_filepath)
        else:
            self._move_item(item.translate_ids['content'], item.content_filepath)

    def create(self, categories):
        for category in categories:
            if not category.translate_ids.get('content'):
                translate_id = self._create_item(category.content_filepath)
                category.translate_ids = {'content': translate_id}
            for section in category.sections:
                if not section.translate_ids.get('content'):
                    translate_id = self._create_item(section.content_filepath)
                    section.translate_ids = {'content': translate_id}
                for article in section.articles:
                    translate_ids = {}
                    if not article.translate_ids.get('content'):
                        translate_id = self._create_item(article.content_filepath)
                        translate_ids['content'] = translate_id
                    if not article.translate_ids.get('body'):
                        translate_id = self._create_item(article.body_filepath)
                        translate_ids['body'] = translate_id
                    article.translate_ids = translate_ids
        return categories

    def fix(self, categories):
        master_files = self.req.get_master_files()
        for category in categories:
            self.fix_group(category, master_files)
            for section in category.sections:
                self.fix_group(section, master_files)
                for article in section.articles:
                    self.fix_article(article, master_files)
        return categories


class Translator(object):

    def __init__(self, req):
        self.client = WebTranslateItClient(req)

    def create(self, categories):
        return self.client.create(categories)


class Remover(object):

    def __init__(self, req):
        self.client = WebTranslateItClient(req)

    def _remove_item(self, item):
        self.client.delete(item)

    # TODO the remove link should be part of the model and this should be one method.
    def _remove_article(self, article):
        self._remove_item(article)

    def _remove_section(self, section):
        self._remove_item(section)
        for article in section.articles:
            self._remove_article(article)

    def _remove_category(self, category):
        self._remove_item(category)
        for section in category.sections:
            self._remove_section(section)

    def remove(self, item):
        # TODO to be improved, read above
        if isinstance(item, model.Article):
            self._remove_article(item)
        if isinstance(item, model.Section):
            self._remove_section(item)
        if isinstance(item, model.Category):
            self._remove_category(item)


class Mover(object):

    def __init__(self, req):
        self.req = req


class Doctor(object):

    def __init__(self, req):
        self.client = WebTranslateItClient(req)

    def fix(self, categories):
        self.client.fix(categories)


def translator(api_key):
    req = WebTranslateItRequest(api_key)
    return Translator(req)


def remover(api_key):
    req = WebTranslateItRequest(api_key)
    return Remover(req)


def mover(api_key):
    req = WebTranslateItRequest(api_key)
    return Mover(req)


def doctor(api_key):
    req = WebTranslateItRequest(api_key)
    return Doctor(req)
