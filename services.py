import os
import markdown
import requests
import shutil
import hashlib
import json
import utils
import exceptions
import logging


class FilesystemService(object):
    _reader = {
        'text': lambda fp: fp.read(),
        'json': lambda fp: json.load(fp)
    }

    _writer = {
        'text': lambda fp, data: fp.write(data),
        'json': lambda fp, data: json.dump(data, fp, indent=4, sort_keys=True)
    }

    def read(self, filepath, file_format='json'):
        if file_format not in self._reader:
            raise exceptions.FileFormatError('Only {} formats are available but {} was given'.format(
                list(self._reader.keys()), file_format))
        if os.path.exists(filepath):
            with open(filepath) as fp:
                logging.debug('Reading file from %s in %s format', filepath, file_format)
                return self._reader[file_format](fp)
        else:
            logging.info('File at %s doesn\'t exist, reading skipped', filepath)
            return {}

    def save(self, filepath, data, file_format='json'):
        if file_format not in self._writer:
            raise exceptions.FileFormatError('Only {} formats are available but {} was given'.format(
                list(self._writer.keys()), file_format))
        with open(filepath, 'w') as fp:
            logging.debug('Saving file to %s in %s format', filepath, file_format)
            return self._writer[file_format](fp, data)

    def remove(self, filepath):
        logging.debug('Removing file from %s', filepath)
        os.remove(filepath)

    def remove_dir(self, dirpath):
        logging.debug('Removing dir tree from %s', dirpath)
        shutil.rmtree(dirpath)

    def move(self, source_path, destination_path):
        logging.debug('moving from %s to %s', source_path, destination_path)
        shutil.move(source_path, destination_path)


class ZendeskRequest(object):
    DEFAULT_URL = 'https://{}.zendesk.com/hc/api/v2/{}'

    def __init__(self, company_name, user, password):
        super().__init__()
        self.company_name = company_name
        self.user = user
        self.password = password

    def url_for(self, path):
        return self.DEFAULT_URL.format(self.company_name, path)

    def get(self, url):
        url = self.url_for(url)
        logging.debug('getting data from %s', url)
        response = requests.get(url, auth=(self.user, self.password))

        if response.status_code == 404:
            logging.info('%s does not exist', url)
            return {}
        if response.status_code != 200:
            raise exceptions.ZendeskException('getting data from {} failed. status was {} and message {}'
                                              .format(url, response.status_code, response.text))
        return response.json()

    def put(self, url, data):
        return self.send_request(requests.put, url, data)

    def post(self, url, data):
        return self.send_request(requests.post, url, data)

    def send_request(self, request_fn, url, data):
        url = self.url_for(url)
        logging.debug('sending request to %s', url)
        response = request_fn(url, data=json.dumps(data),
                              auth=(self.user, self.password),
                              headers={'Content-type': 'application/json'})
        if response.status_code not in [200, 201]:
            raise exceptions.ZendeskException('sending requests at {} failed. status was {} and message {}'
                                              .format(url, response.status_code, response.text))
        return response.json()

    def delete(self, url):
        url = self.url_for(url)
        response = requests.delete(url, auth=(self.user, self.password))
        return response.status_code == 200


class ZendeskService(object):

    """
    Handles all requests to Zendesk
    """

    def __init__(self, req=None):
        super().__init__()
        self.req = req

    def fetch_categories(self):
        print(type(self.req))
        return self.req.get('categories.json')['categories']

    def fetch_sections(self, category_id):
        return self.req.get('categories/{}/sections.json'.format(category_id))['sections']

    def fetch_articles(self, section_id):
        return self.req.get('sections/{}/articles.json'.format(section_id))['articles']

    def update_category(self, category):
        logging.debug('updating category')
        return self._update_group(category, 'categories/{}/translations{}.json',
                                  'categories/{}/translations/missing.json')

    def update_section(self, section):
        logging.debug('updating section')
        return self._update_group(section, 'sections/{}/translations{}.json', 'sections/{}/translations/missing.json')

    def update_article(self, article, cdn_path):
        logging.debug('updating article')
        translation_url = 'articles/{}/translations{}.json'
        article_id = article.zendesk_id
        self._disable_article_comments(article)
        translations = self._article_translations(article.translations, cdn_path)
        missing_url = 'articles/{}/translations/missing.json'
        return self._translate(translation_url, missing_url, article_id, translations)

    def _disable_article_comments(self, article):
        article_id = article.zendesk_id
        data = {
            'comments_disabled': article.comments_disabled
        }
        self.req.put('articles/{}.json'.format(article_id), data)

    def _update_group(self, group, url, missing_url):
        group_id = group.zendesk_id
        translations = self._group_translations(group.translations)
        return self._translate(url, missing_url, group_id, translations)

    def _group_translations(self, translations):
        result = []
        for locale, filepath in translations.items():
            with open(filepath, 'r') as file:
                file_data = json.load(file)
                translation = {
                    'title': file_data['name'] or '',
                    'body': file_data['description'] or '',
                    'locale': utils.to_zendesk_locale(locale or utils.DEFAULT_LOCALE)
                }
                result.append(translation)
        logging.debug('translations for group %s are %s', filepath, result)
        return result

    def _article_translations(self, translations, cdn_path):
        result = []
        for locale, (content_filepath, body_filepath) in translations.items():
            with open(content_filepath, 'r') as file:
                file_data = json.load(file)
                article_name = file_data['name']
            with open(body_filepath, 'r') as file:
                file_data = file.read()
                file_data = utils.convert_to_cdn_path(cdn_path, file_data)
                article_body = markdown.markdown(file_data)
            translation = {
                'title': article_name or '',
                'body': article_body or '',
                'locale': utils.to_zendesk_locale(locale or utils.DEFAULT_LOCALE)
            }
            result.append(translation)
        logging.debug('translations for article %s are %s', content_filepath, result)
        return result

    def _translate(self, url, missing_url, item_id, translations):
        missing_locales = self.req.get(missing_url.format(item_id))['locales']
        logging.debug('missing locales for %s are %s', item_id, missing_locales)
        for translation in translations:
            locale = utils.to_zendesk_locale(translation['locale'])
            if locale in missing_locales:
                self.req.send_request(
                    requests.post, url.format(item_id, ''), {'translation': translation})['translation']
            else:
                if self._has_content_changed(url.format(item_id, ''), translation):
                    self.req.send_request(requests.put, url.format(item_id, '/' + locale), translation)['translation']
                else:
                    logging.debug('skipping as nothing changed for translation %s', url.format(item_id, ''))

    def _has_content_changed(self, url, translation):
        content = self.req.get(url).get('translation', {})
        for key in ['body', 'title']:
            content_body = content.get(key, '')
            content_hash = hashlib.md5(content_body.encode('utf-8'))
            translation_hash = hashlib.md5(translation[key].encode('utf-8'))
            if content_hash.hexdigest() != translation_hash.hexdigest():
                return True
        return False

    def available_locales(self):
        return self.req.get('locales.json')['locales']

    def create_category(self, translations):
        url = 'categories.json'
        logging.debug('creating new category')
        data = {
            'category': {
                'translations': self._group_translations(translations)
            }
        }
        return self.req.post(url, data)['category']

    def create_section(self, category_id, translations):
        url = 'categories/{}/sections.json'.format(category_id)
        logging.debug('creating new section')
        data = {
            'section': {
                'translations': self._group_translations(translations)
            }
        }
        return self.req.post(url, data)['section']

    def create_article(self, section_id, cdn_path, comments_disabled, translations):
        url = 'sections/{}/articles.json'.format(section_id)
        logging.debug('creating new article')
        data = {
            'article': {
                'translations': self._article_translations(translations, cdn_path),
                'comments_disabled': comments_disabled
            }
        }
        return self.req.post(url, data)['article']

    def delete_article(self, article_id):
        logging.debug('deleting article')
        return self.req.delete('articles/{}.json'.format(article_id))

    def delete_section(self, section_id):
        logging.debug('deleting section')
        return self.req.delete('sections/{}.json'.format(section_id))

    def delete_category(self, category_id):
        logging.debug('deleting category')
        return self.req.delete('categories/{}.json'.format(category_id))

    def move_article(self, article_id, section_id):
        logging.debug('moving article')
        data = {
            'article': {
                'section_id': section_id
            }
        }
        self.req.put('articles/{}.json'.format(article_id), data)

    def move_section(self, section_id, category_id):
        logging.debug('moving section')
        data = {
            'section': {
                'category_id': category_id
            }
        }
        self.req.put('sections/{}.json'.format(section_id), data)


class WebTranslateItService(object):

    """
    Handles all reuests to WebTranslateIt
    """
    DEFAULT_URL = 'https://webtranslateit.com/api/projects/{}/{}'

    def __init__(self):
        self.api_key = ''

    def url_for(self, path):
        return WebTranslateItService.DEFAULT_URL.format(self.api_key, path)

    def create(self, filepath):
        with open(filepath, 'r') as file:
            normalized_filepath = os.path.relpath(filepath).replace('\\', '/')
            url = self.url_for('files')
            logging.debug('upload file %s for transaltion to %s', normalized_filepath, url)
            response = requests.post(url,
                                     data={'file': normalized_filepath, 'name': normalized_filepath},
                                     files={'file': file})

            if response.status_code == 200:
                return response.text.strip()
            return ''

    def delete(self, file_ids):
        for file_id in file_ids:
            url = self.url_for('files/' + file_id)
            logging.debug('removing file {} from {}', file_id, url)
            requests.delete(url)

    def move(self, file_id, new_path):
        with open(new_path, 'r') as file:
            normalized_new_path = new_path.replace('\\', '/')
            url = self.url_for('files/{}/locales/en'.format(file_id))
            logging.debug('update file %s for transaltion', normalized_new_path)
            requests.put(url,
                         data={'file': normalized_new_path, 'name': normalized_new_path},
                         files={'file': file})

filesystem = FilesystemService()
zendesk = ZendeskService()
translate = WebTranslateItService()
