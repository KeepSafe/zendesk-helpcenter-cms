import os
import markdown
import requests
import shutil
import json
import utils

LOG = utils.Logger()


class MetaService(object):

    """
    Handles all meta content, meaning the content coming from Zendesk. Normally just dumps json from Zendesk to a file
    and reads whatever is needed from there. Also has some utility methods which requite meta info.
    """

    def read(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                return json.load(file)
        return None

    def save(self, filepath, data):
        with open(filepath, 'w') as file:
            LOG.info('saving meta info {} to path {}', data['name'], filepath)
            json.dump(data, file, indent=4, sort_keys=True)

    def remove(self, filepath):
        LOG.debug('removing file {}', filepath)
        os.remove(filepath)

    def move(self, source, destination):
        shutil.move(source, destination)


class ContentService(object):

    """
    Handles all content, meaning the stuff that is used to create categories and articles. Categories and sections use
    special file to hold name and description.
    """

    def save(self, filepath, data):
        if not os.path.exists(filepath):
            with open(filepath, 'w') as file:
                file.write(data)
            LOG.info('saving content to path {}', filepath)
        else:
            LOG.info('content at path {} already exists, skipping...', filepath)

    def read(self, filepath):
        with open(filepath, 'r') as file:
            LOG.info('reading content from path {}', filepath)
            return file.read()

    def remove(self, filepath):
        LOG.debug('removing file {}', filepath)
        os.remove(filepath)

    def remove_group(self, filepath):
        LOG.debug('removing folder {}', filepath)
        shutil.rmtree(filepath)

    def move(self, source, destination):
        shutil.move(source, destination)


class ZendeskService(object):

    """
    Handles all requests to Zendesk
    """
    DEFAULT_URL = 'https://{}.zendesk.com/hc/api/v2/{}'

    def __init__(self, options):
        super().__init__()
        self.options = options

    def url_for(self, path):
        return ZendeskService.DEFAULT_URL.format(self.options['company_name'], path)

    def _fetch(self, url):
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception('there was a problem fetching data from {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        return response.json()

    def fetch_categories(self):
        url = self.url_for('categories.json')
        LOG.debug('fetching categories from {}', url)
        return self._fetch(url)['categories']

    def fetch_sections(self, category_id):
        url = self.url_for('categories/{}/sections.json'.format(category_id))
        LOG.debug('fetching sections from {}', url)
        return self._fetch(url)['sections']

    def fetch_articles(self, section_id):
        url = self.url_for('sections/{}/articles.json'.format(section_id))
        LOG.debug('fetching articles from {}', url)
        return self._fetch(url)['articles']

    def update_category(self, category):
        return self._update_group(category, 'categories/{}/translations{}.json',
                                  'categories/{}/translations/missing.json')

    def update_section(self, section):
        return self._update_group(section, 'sections/{}/translations{}.json', 'sections/{}/translations/missing.json')

    def update_article(self, article):
        url = 'articles/{}/translations{}.json'
        article_id = article.zendesk_id
        translations = self._article_translations(article.translations)
        missing_url = self.url_for('articles/{}/translations/missing.json'.format(article_id))
        return self._translate(url, missing_url, article_id, translations)

    def _update_group(self, group, url, missing_url):
        group_id = group.zendesk_id
        translations = self._group_translations(group.translations)
        full_missing_url = self.url_for(missing_url.format(group_id))
        return self._translate(url, full_missing_url, group_id, translations)

    def _group_translations(self, translations):
        result = []
        for locale, filepath in translations.items():
            with open(filepath, 'r') as file:
                file_data = json.load(file)
                translation = {
                    'title': file_data['name'],
                    'body': file_data['description'],
                    'locale': locale
                }
                result.append(translation)
        LOG.debug('translations for group {} are {}', filepath, result)
        return result

    def _article_translations(self, translations):
        result = []
        for locale, (body_filepath, content_filepath) in translations.items():
            with open(content_filepath, 'r') as file:
                file_data = json.load(file)
                article_name = file_data['name']
            with open(body_filepath, 'r') as file:
                file_data = file.read()
                article_body = markdown.markdown(file_data)
            translation = {
                'title': article_name,
                'body': article_body,
                'locale': locale
            }
            result.append(translation)
        LOG.debug('translations for article {} are {}', content_filepath, result)
        return result

    def _translate(self, url, missing_url, item_id, translations):
        missing_locales = self._missing_locales(missing_url)
        LOG.debug('missing locales for {} are {}', item_id, missing_locales)
        for translation in translations:
            locale = translation['locale']
            if locale in missing_locales:
                create_url = self.url_for(url.format(item_id, ''))
                LOG.debug('creating translation at {}', create_url)
                self._send_translate_request(create_url, {'translation': translation}, requests.post)
            else:
                update_url = self.url_for(url.format(item_id, '/' + locale))
                LOG.debug('updating translation at {}', update_url)
                self._send_translate_request(update_url, translation, requests.put)

    def _send_translate_request(self, url, translation_data, request_fn):
        response = request_fn(url, data=json.dumps(translation_data),
                              auth=(self.options['user'], self.options['password']),
                              headers={'Content-type': 'application/json'})
        if response.status_code not in [200, 201]:
            raise Exception('there was a problem uploading translations at {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        response_data = response.json()
        return response_data['translation']

    def _missing_locales(self, url):
        response = requests.get(url, auth=(self.options['user'], self.options['password']),
                                headers={'Content-type': 'application/json'})
        if response.status_code != 200:
            raise Exception('there was a problem fetching missng locales from {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        response_data = response.json()
        return response_data['locales']

    def _create(self, url, data):
        response = requests.post(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                                 headers={'Content-type': 'application/json'})
        if response.status_code != 201:
            raise Exception('there was a problem creating an item at {}. status was {} and message {}'
                            .format(url, response.status_code, response.text))
        return response.json()

    def create_category(self, translations):
        url = self.url_for('categories.json')
        LOG.debug('creating new category at {}', url)
        data = {
            'category': {
                'translations': self._group_translations(translations)
            }
        }
        return self._create(url, data)['category']

    def create_section(self, category_id, translations):
        url = self.url_for('categories/{}/sections.json'.format(category_id))
        LOG.debug('creating new section at {}', url)
        data = {
            'section': {
                'translations': self._group_translations(translations)
            }
        }
        return self._create(url, data)['section']

    def create_article(self, section_id, translations):
        url = self.url_for('sections/{}/articles.json'.format(section_id))
        LOG.debug('creating new article at {}', url)
        data = {
            'article': {
                'translations': self._article_translations(translations)
            }
        }
        return self._create(url, data)['article']

    def delete_article(self, article_id):
        url = self.url_for('articles/{}.json'.format(article_id))
        LOG.debug('deleting article from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        return response.status_code == 200

    def delete_section(self, section_id):
        url = self.url_for('sections/{}.json'.format(section_id))
        LOG.debug('deleting section from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        return response.status_code == 200

    def delete_category(self, category_id):
        url = self.url_for('categories/{}.json'.format(category_id))
        LOG.debug('deleting category from {}', url)
        response = requests.delete(url, auth=(self.options['user'], self.options['password']))
        return response.status_code == 200

    def move_article(self, article_id, section_id):
        url = self.url_for('articles/{}.json'.format(article_id))
        LOG.debug('moving article {}', url)
        data = {
            'article': {
                'section_id': section_id
            }
        }
        requests.put(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                     headers={'Content-type': 'application/json'})

    def move_section(self, section_id, category_id):
        url = self.url_for('sections/{}.json'.format(section_id))
        LOG.debug('moving section {}', url)
        data = {
            'section': {
                'category_id': category_id
            }
        }
        requests.put(url, data=json.dumps(data), auth=(self.options['user'], self.options['password']),
                     headers={'Content-type': 'application/json'})

    def download_article_attachments(self, article_id, attachments_path):
        url = self.url_for('articles/{}/attachments.json'.format(article_id))
        response = requests.get(url, auth=(self.options['user'], self.options['password']))
        attachments = response.json()
        for attachment in attachments['article_attachments']:
            content_url = attachment['content_url']
            response = requests.get(content_url, stream=True)
            with open(os.path.join(attachments_path, attachment['file_name']), 'w') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)


class WebTranslateItService(object):

    """
    Handles all reuests to WebTranslateIt
    """
    DEFAULT_URL = 'https://webtranslateit.com/api/projects/{}/{}'

    def __init__(self, options):
        self.api_key = options['webtranslateit_api_key']

    def url_for(self, path):
        return WebTranslateItService.DEFAULT_URL.format(self.api_key, path)

    def create(self, filepath):
        with open(filepath, 'r') as file:
            normalized_filepath = filepath.replace('\\', '/')
            url = self.url_for('files')
            LOG.debug('upload file {} for transaltion to {}', normalized_filepath, url)
            response = requests.post(url,
                                     data={'file': normalized_filepath, 'name': normalized_filepath},
                                     files={'file': file})
            if response.status_code == 200:
                return str(response.json())
            return None

    def delete(self, file_ids):
        for file_id in file_ids:
            url = self.url_for('files/' + file_id)
            LOG.debug('removing file {} from {}', file_id, url)
            requests.delete(url)

    def move(self, file_id, new_path):
        with open(new_path, 'r') as file:
            normalized_new_path = new_path.replace('\\', '/')
            url = self.url_for('files/{}/locales/en'.format(file_id))
            LOG.debug('update file {} for transaltion', normalized_new_path)
            requests.put(url,
                         data={'file': normalized_new_path, 'name': normalized_new_path},
                         files={'file': file})
