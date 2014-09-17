import logging
import requests
import json
import html2text
import hashlib

import model
import utils


class ZendeskRequest(object):
    _default_url = 'https://{}.zendesk.com/hc/api/v2/{}'

    def __init__(self, company_name, user, password):
        super().__init__()
        self.company_name = company_name
        self.user = user
        self.password = password

    def _url_for(self, path):
        return self._default_url.format(self.company_name, path)

    def _parse_response(self, response):
        if response.status_code == 404:
            raise RecordNotFoundError('Missing record for {}'.format(response.url))
        if response.status_code not in [200, 201]:
            logging.error('getting data from %s failed. status was %s and message %s',
                          response.url, response.status_code, response.text)
            return {}

        return response.json()

    def _send_request(self, request_fn, url, data):
        full_url = self._url_for(url)
        response = request_fn(full_url, data=json.dumps(data),
                              auth=(self.user, self.password),
                              headers={'Content-type': 'application/json'})
        return self._parse_response(response)

    def get(self, url):
        full_url = self._url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password))
        return self._parse_response(response)

    def put(self, url, data):
        return self._send_request(requests.put, url, data)

    def post(self, url, data):
        return self._send_request(requests.post, url, data)

    def delete(self, url):
        full_url = self.url_for(url)
        response = requests.delete(full_url, auth=(self.user, self.password))
        return response.status_code == 200


class Fetcher(object):

    def __init__(self, req):
        super().__init__()
        self.req = req

    def _fetch_categories(self):
        return self.req.get('categories.json')['categories']

    def _fetch_sections(self, category):
        return self.req.get('categories/{}/sections.json'.format(category.zendesk_id))['sections']

    def _fetch_articles(self, section):
        return self.req.get('sections/{}/articles.json'.format(section.zendesk_id))['articles']

    def fetch(self):
        categories = []
        zendesk_categories = self._fetch_categories()
        for zendesk_category in zendesk_categories:
            category_filename = utils.slugify(zendesk_category['name'])
            category = model.Category(zendesk_category['name'], zendesk_category['description'], category_filename)
            print('Category %s created' % category.name)
            category.meta = zendesk_category
            zendesk_sections = self._fetch_sections(category)
            categories.append(category)
            for zendesk_section in zendesk_sections:
                section_filename = utils.slugify(zendesk_section['name'])
                section = model.Section(category, zendesk_section['name'],
                                        zendesk_section['description'], section_filename)
                print('Section %s created' % section.name)
                section.meta = zendesk_section
                zendesk_articles = self._fetch_articles(section)
                category.sections.append(section)
                for zendesk_article in zendesk_articles:
                    body = html2text.html2text(zendesk_article['body'])
                    article_filename = utils.slugify(zendesk_article['title'])
                    article = model.Article(section, zendesk_article['title'], body, article_filename)
                    print('Article %s created' % article.name)
                    article.meta = zendesk_article
                    section.articles.append(article)
        return categories


class Pusher(object):
    _missing_translation_url = '{}/{}/translations/missing.json'
    _update_translation_url = '{}/{}/translations/{}.json'
    _new_translation_url = '{}/{}/translations.json'
    _update_item_url = '{}/{}.json'

    def __init__(self, req, fs, image_cdn):
        self.req = req
        self.fs = fs
        self.image_cdn = image_cdn

    def _has_content_changed(self, item, zendesk_id, endpoint, key, locale):
        url = self._update_translation_url.format(endpoint, zendesk_id, locale)
        content = self.req.get(url).get('translation', {})
        item_content = item.to_dict(self.image_cdn)
        for key in item_content:
            content_body = content.get(key) or ''
            content_hash = hashlib.md5(content_body.encode('utf-8'))
            translation_hash = hashlib.md5(item_content[key].encode('utf-8'))
            if content_hash.hexdigest() != translation_hash.hexdigest():
                return True
        return False

    def _push_new_item(self, item, endpoint, key):
        data = {key: item.to_dict(self.image_cdn)}
        meta = self.req.post(item.new_item_url, data)[key]
        item.meta = meta
        self.fs.save_json(item.meta_filepath, meta)

    def _push_item_translations(self, item, endpoint, key):
        missing_url = self._missing_translation_url.format(endpoint, item.zendesk_id)
        missing_locales = self.req.get(missing_url)['locales']
        for translation in item.translations:
            locale = utils.to_zendesk_locale(translation.locale)
            data = {'translation': translation.to_dict(self.image_cdn)}
            if locale in missing_locales:
                url = self._new_translation_url.format(endpoint, item.zendesk_id)
                print('New translation for locale {}'.format(translation.locale))
                self.req.post(url, data)
            else:
                if self._has_content_changed(translation, item.zendesk_id, endpoint, key, locale):
                    url = self._update_translation_url.format(endpoint, item.zendesk_id, locale)
                    print('Updating translation for locale {}'.format(translation.locale))
                    self.req.put(url, data)
                else:
                    print('Nothing changed for locale {}'.format(translation.locale))

    def _push(self, item, endpoint, key):
        if not item.zendesk_id:
            self._push_new_item(item, endpoint, key)
        self._push_item_translations(item, endpoint, key)

    def _push_category(self, category):
        print('Pushing category %s' % category.name)
        self._push(category, 'categories', 'category')

    def _push_section(self, section):
        print('Pushing section %s' % section.name)
        self._push(section, 'sections', 'section')

    # TODO code dup, needs to pass image_cdn smarter
    def _push_article(self, article):
        print('Pushing article %s' % article.name)
        self._push(article, 'articles', 'article')

    def push(self, categories):
        for category in categories:
            self._push_category(category)
            for section in category.sections:
                self._push_section(section)
                for article in section.articles:
                    self._push_article(article)


class Remover(object):

    def __init__(self, req):
        self.req = req

    # TODO the remove link should be part of the model and this should be one method.
    def _remove_article(self, article):
        self.req.delete('articles/{}.json'.format(article.zendesk_id))

    def _remove_section(self, section):
        self.req.delete('sections/{}.json'.format(section.zendesk_id))

    def _remove_category(self, category):
        self.req.delete('categories/{}.json'.format(category.zendesk_id))

    def remove(self, item):
        # TODO to be improved, read above
        if isinstance(item, model.Article):
            self._remove_article(item)
        if isinstance(item, model.Section):
            self._remove_section(item)
        if isinstance(item, model.Category):
            self._remove_category(item)


class Doctor(object):

    def __init__(self, req, fs):
        self.req = req
        self.fs = fs

    def _fetch_item(self, item, key):
        res = self.req.get('{}.json'.format(key))
        zendesk_items = res[key]
        for zendesk_item in zendesk_items:
            if zendesk_item['name'] == item.name:
                item.meta = zendesk_item
                self.fs.save_json(item.meta_filepath, item.meta)
                return True
        return False

    def _exists(self, item, key):
        try:
            self.req.get('{}/{}.json'.format(key, item.zendesk_id))
        except RecordNotFoundError:
            return False
        return True

    def _fix_item(self, item, key):
        if not item.zendesk_id:
            if self._fetch_item(item, key):
                print('Zendesk ID is missing but found item with the same name {}.'
                      ' If this is not corrent you need to fix it manually'.format(item.name))
        else:
            if not self._exists(item, key):
                if self._fetch_item(item, key):
                    print('Zendesk ID is incorrect but found item with the same name {}.'
                          ' If this is not corrent you need to fix it manually'.format(item.name))
                else:
                    print('Zendesk ID is incorrect but no item with the same name'
                          ' was found for name {}. Assuming new item'.format(item.name))
                    self.fs.remove(item.meta_filepath)

    def fix_category(self, category):
        self._fix_item(category, 'categories')

    def fix_section(self, section):
        self._fix_item(section, 'sections')

    def fix_article(self, article):
        self._fix_item(article, 'articles')


class RecordNotFoundError(Exception):
    pass


def fetcher(company_name, user, password):
    req = ZendeskRequest(company_name, user, password)
    return Fetcher(req)


def pusher(company_name, user, password, fs, image_cdn):
    req = ZendeskRequest(company_name, user, password)
    return Pusher(req, fs, image_cdn)


def remover(company_name, user, password):
    req = ZendeskRequest(company_name, user, password)
    return Remover(req)


def doctor(company_name, user, password, fs):
    req = ZendeskRequest(company_name, user, password)
    return Doctor(req, fs)
