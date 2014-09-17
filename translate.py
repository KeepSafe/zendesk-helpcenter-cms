import os
import requests
import logging

import model


class WebTranslateItRequest(object):
    _default_url = 'https://webtranslateit.com/api/projects/{}/{}'

    def __init__(self, api_key):
        self.api_key = api_key

    def _url_for(self, path):
        return self._default_url.format(self.api_key, path)

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
        self._send_request(requests.post, url, data, files)

    def put(self, url, data, files=None):
        self._send_request(requests.put, url, data, files)

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
            self.req.post('files', data, files)

    def _move_item(self, file_id, filepath):
        with open(filepath, 'r') as file:
            normalized_new_path = filepath.replace('\\', '/')
            data = {'file': normalized_new_path, 'name': normalized_new_path}
            files = {'file': file}
            self.req.put('files/{}/locales/{}'.format(file_id, model.DEFAULT_LOCALE), data, files)

    def delete(self, item):
        for file_id in item.translate_ids:
            self.req.delete('files/{}'.format(file_id))

    def move(self, item, new_path):
        # Guido weeps
        if isinstance(item, model.Article):
            body_translate_id, content_translate_id = item.translate_ids
            self._move_item(body_translate_id, item.body_filepath)
            self._move_item(content_translate_id, item.content_filepath)
        else:
            content_translate_id, = item.translate_ids
            self._move_item(content_translate_id, item.content_filepath)

    def create(self, categories):
        for category in categories:
            self._create_item(category.content_filepath)
            for section in category.sections:
                self._create_item(section.content_filepath)
                for article in section.articles:
                    self._create_item(article.content_filepath)
                    self._create_item(article.body_filepath)


class Remover(object):
    def __init__(self, req):
        self.req = req

    def _remove_item(self, item):
        for translate_id in item.translate_ids:
            self.req.delete('files/' + translate_id)

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


class Doctor(object):
    def __init__(self, req):
        self.req = req

    def fix_category(self, category):
        pass

    def fix_section(self, section):
        pass

    def fix_article(self, article):
        pass


def translator(api_key):
    req = WebTranslateItRequest(api_key)
    return WebTranslateItClient(req)


def remover(api_key):
    req = WebTranslateItRequest(api_key)
    return Remover(req)


def doctor(api_key):
    req = WebTranslateItRequest(api_key)
    return Doctor(req)
