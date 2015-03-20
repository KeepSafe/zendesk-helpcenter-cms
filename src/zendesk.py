import logging
import requests
import json
import html2text
import hashlib

import model
import utils


class ZendeskRequest(object):
    _default_url = 'https://{}.zendesk.com/api/v2/help_center/' + utils.to_zendesk_locale(model.DEFAULT_LOCALE) + '/{}'
    _translations_url = 'https://{}.zendesk.com/api/v2/help_center/{}'

    item_url = '{}/{}.json'
    items_url = '{}.json?per_page=100'
    items_in_group_url = '{}/{}/{}.json?per_page=100'

    translation_url = '{}/{}/translations/{}.json'
    translations_url = '{}/{}/translations.json?per_page=100'
    missing_translations_url = '{}/{}/translations/missing.json'

    def __init__(self, company_name, user, password):
        super().__init__()
        self.company_name = company_name
        self.user = user
        self.password = password

    def _url_for(self, path):
        return self._default_url.format(self.company_name, path)

    def _translation_url_for(self, path):
        return self._translations_url.format(self.company_name, path)

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

    def _send_translation(self, request_fn, url, data):
        full_url = self._translation_url_for(url)
        response = request_fn(full_url, data=json.dumps(data),
                              auth=(self.user, self.password),
                              headers={'Content-type': 'application/json'})
        return self._parse_response(response)

    def get_item(self, item):
        url = self.item_url.format(item.zendesk_group, item.zendesk_id)
        full_url = self._url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password))
        return self._parse_response(response).get(item.zendesk_name, {})

    def get_items(self, item, parent=None):
        if parent:
            url = self.items_in_group_url.format(parent.zendesk_group, parent.zendesk_id, item.zendesk_group)
        else:
            url = self.items_url.format(item.zendesk_group)
        full_url = self._url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password))
        return self._parse_response(response).get(item.zendesk_group, {})

    def get_missing_locales(self, item):
        url = self.missing_translations_url.format(item.zendesk_group, item.zendesk_id)
        full_url = self._translation_url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password))
        return self._parse_response(response).get('locales', [])

    def get_translation(self, item, locale):
        url = self.translation_url.format(item.zendesk_group, item.zendesk_id, locale)
        full_url = self._translation_url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password))
        return self._parse_response(response).get('translation', {})

    def put(self, item, data):
        url = self.item_url.format(item.zendesk_group, item.zendesk_id)
        return self._send_request(requests.put, url, data).get(item.zendesk_name, {})

    def put_translation(self, item, locale, data):
        url = self.translation_url.format(item.zendesk_group, item.zendesk_id, locale)
        return self._send_translation(requests.put, url, data).get('translation', {})

    def post(self, item, data, parent=None):
        if parent:
            url = self.items_in_group_url.format(parent.zendesk_group, parent.zendesk_id, item.zendesk_group)
        else:
            url = self.items_url.format(item.zendesk_group)
        return self._send_request(requests.post, url, data).get(item.zendesk_name, {})

    def post_translation(self, item, data):
        url = self.translations_url.format(item.zendesk_group, item.zendesk_id)
        return self._send_translation(requests.post, url, data).get('translation', {})

    def delete(self, item):
        url = self.item_url.format(item.zendesk_group, item.zendesk_id)
        full_url = self._url_for(url)
        return self.raw_delete(full_url)

    def raw_delete(self, full_url):
        response = requests.delete(full_url, auth=(self.user, self.password))
        return response.status_code == 200


class Fetcher(object):

    def __init__(self, req):
        super().__init__()
        self.req = req

    def fetch(self):
        categories = []
        zendesk_categories = self.req.get_items(model.Category)
        for zendesk_category in zendesk_categories:
            category_filename = utils.slugify(zendesk_category['name'])
            category = model.Category(zendesk_category['name'], zendesk_category['description'], category_filename)
            print('Category %s created' % category.name)
            category.meta = zendesk_category
            zendesk_sections = self.req.get_items(model.Section, category)
            categories.append(category)
            for zendesk_section in zendesk_sections:
                section_filename = utils.slugify(zendesk_section['name'])
                section = model.Section(category, zendesk_section['name'],
                                        zendesk_section['description'], section_filename)
                print('Section %s created' % section.name)
                section.meta = zendesk_section
                zendesk_articles = self.req.get_items(model.Article, section)
                category.sections.append(section)
                for zendesk_article in zendesk_articles:
                    body = html2text.html2text(zendesk_article.get('body', ''))
                    article_filename = utils.slugify(zendesk_article['title'])
                    article = model.Article(section, zendesk_article['title'], body, article_filename)
                    print('Article %s created' % article.name)
                    article.meta = zendesk_article
                    section.articles.append(article)
        return categories


class Pusher(object):

    def __init__(self, req, fs, image_cdn, disable_comments):
        self.req = req
        self.fs = fs
        self.image_cdn = image_cdn
        self.disable_comments = disable_comments

    def _has_content_changed(self, translation, item, locale):
        zendesk_content = self.req.get_translation(item, locale)
        item_content = translation.to_dict(self.image_cdn)
        for key in item_content:
            zendesk_body = zendesk_content.get(key, '')
            zendesk_hash = hashlib.md5(zendesk_body.encode('utf-8'))
            item_hash = hashlib.md5(item_content[key].encode('utf-8'))
            if zendesk_hash.hexdigest() != item_hash.hexdigest():
                return True
        return False

    def _push_new_item(self, item, parent=None):
        data = {item.zendesk_name: item.to_dict(self.image_cdn)}
        meta = self.req.post(item, data, parent)
        meta = self.fs.save_json(item.meta_filepath, meta)
        item.meta = meta

    def _push_item_translations(self, item):
        missing_locales = self.req.get_missing_locales(item)
        for translation in item.translations:
            locale = utils.to_zendesk_locale(translation.locale)
            data = {'translation': translation.to_dict(self.image_cdn)}
            if locale in missing_locales:
                print('New translation for locale {}'.format(translation.locale))
                self.req.post_translation(item, data)
            else:
                if self._has_content_changed(translation, item, locale):
                    print('Updating translation for locale {}'.format(translation.locale))
                    self.req.put_translation(item, locale, data)
                else:
                    print('Nothing changed for locale {}'.format(translation.locale))

    def _disable_article_comments(self, article):
        data = {
            'comments_disabled': True
        }
        self.req.put(article, data)

    def _push(self, item, parent=None):
        if not item.zendesk_id:
            self._push_new_item(item, parent)
        self._push_item_translations(item)

    def push(self, categories):
        for category in categories:
            print('Pushing category %s' % category.name)
            self._push(category)
            for section in category.sections:
                print('Pushing section %s' % section.name)
                self._push(section, category)
                for article in section.articles:
                    print('Pushing article %s' % article.name)
                    self._push(article, section)
                    if self.disable_comments:
                        self._disable_article_comments(article)


class Remover(object):

    def __init__(self, req):
        self.req = req

    def remove(self, item):
        if item.zendesk_id:
            self.req.delete(item)


class Mover(object):

    def __init__(self, req, image_cdn):
        self.req = req
        self.image_cdn = image_cdn

    def move(self, item):
        self.req.put(item)


class Doctor(object):

    def __init__(self, req, fs, force=False):
        self.req = req
        self.fs = fs
        self.force = force

    def _merge_items(self, zendesk_items):
        merge = None
        item_paths = [i['name'] for i in zendesk_items]
        if self.force:
            print('There are {} entries with the same name {}, this should be an error. Since the command was run '
                  'with --force option enabled every entry except the oldest will be removed'.format(
                      len(zendesk_items), item_paths))
        else:
            merge = input(
                'There are {} entries with the same name {}. Do you want only the oldest to be kept? (y/n)'.format(
                    len(zendesk_items), item_paths))
        merge = (merge == 'y') or self.force

        while merge and len(zendesk_items) > 1:
            first = zendesk_items[0]
            second = zendesk_items[1]
            if first['created_at'] > second['created_at']:
                self.req.raw_delete(first['url'])
                del zendesk_items[0]
            else:
                self.req.raw_delete(second['url'])
                del zendesk_items[1]
        return zendesk_items

    def _fetch_item(self, item, parent=None):
        zendesk_items = self.req.get_items(item, parent)
        named_items = list(filter(lambda i: i['name'] == item.name, zendesk_items))
        if len(named_items) > 1:
            named_items = self._merge_items(named_items)
        if len(named_items) == 1:
            return named_items[0]
        return {}

    def _exists(self, item):
        try:
            self.req.get_item(item)
        except RecordNotFoundError:
            return False
        return True

    def _fix_item(self, item, parent=None):
        # parent is a new item so this is a new item as well
        if parent and not parent.zendesk_id:
            if item.zendesk_id:
                logging.warning('Parent is a new item but Zendesk ID exists. Removing meta...')
            self.fs.remove(item.meta_filepath)
            item.meta = {}
            return

        try:
            zendesk_item = self._fetch_item(item, parent)
            if item.zendesk_id:
                if zendesk_item and zendesk_item.get('id') != item.zendesk_id:
                    print('Zendesk ID is incorrect but found item with the same name {}.'
                          ' If this is not corrent you need to fix it manually'.format(item.name))
                    item.meta = zendesk_item
                    self.fs.save_json(item.meta_filepath, zendesk_item)
                elif not zendesk_item:
                    print('Zendesk ID is incorrect and no item with the same name'
                          ' was found for name {}. Assuming new item'.format(item.name))
                    self.fs.remove(item.meta_filepath)
                    item.meta = {}
            else:
                if zendesk_item:
                    print('Zendesk ID is missing but found item with the same name {}.'
                          ' If this is not correct you need to fix it manually'.format(item.name))
                    item.meta = zendesk_item
                    self.fs.save_json(item.meta_filepath, zendesk_item)

        except RecordNotFoundError as e:
            logging.warning(str(e))

    def fix(self, categories):
        for category in categories:
            self._fix_item(category)
            for section in category.sections:
                self._fix_item(section, section.category)
                for article in section.articles:
                    self._fix_item(article, article.section)


class RecordNotFoundError(Exception):
    pass


def fetcher(company_name, user, password):
    req = ZendeskRequest(company_name, user, password)
    return Fetcher(req)


def pusher(company_name, user, password, fs, image_cdn, disable_comments):
    req = ZendeskRequest(company_name, user, password)
    return Pusher(req, fs, image_cdn, disable_comments)


def remover(company_name, user, password):
    req = ZendeskRequest(company_name, user, password)
    return Remover(req)


def mover(company_name, user, password, image_cdn):
    req = ZendeskRequest(company_name, user, password)
    return Mover(req, image_cdn)


def doctor(company_name, user, password, fs, force):
    req = ZendeskRequest(company_name, user, password)
    return Doctor(req, fs, force)
