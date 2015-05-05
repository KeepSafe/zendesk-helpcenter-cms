from unittest import TestCase
from unittest.mock import MagicMock, patch
import tempfile
import shutil
import os

from model import Category, Section, Article
import filesystem
import cms


def _create_structure():
    category = Category('test category', 'category test', 'test_category')
    category.meta = {'id': 1, 'webtranslateit_ids': {'content': 1}}
    section = Section(category, 'test section', 'section test', 'test_section')
    section.meta = {'id': 2, 'webtranslateit_ids': {'content': 2}}
    category.sections.append(section)
    article = Article(section, 'test article', 'article body', 'test_article')
    article.meta = {'id': 3, 'webtranslateit_ids': {'content': 3, 'body': 4}}
    section.articles.append(article)
    return category, section, article


class TestRemoveTask(TestCase):
    def setUp(self):
        self.root_folder = tempfile.mkdtemp()
        self.args = {
            'company_uri': 'test_company.com',
            'user': 'test_user',
            'password': 'test_password',
            'webtranslateit_api_key': 'test_key',
            'root_folder': self.root_folder
        }
        self.category, self.section, self.article = _create_structure()
        filesystem.saver(self.root_folder).save([self.category])
        self.task = cms.RemoveTask()

    def tearDown(self):
        shutil.rmtree(self.root_folder)

    def _exists(self, path):
        return os.path.exists(os.path.join(self.root_folder, path))

    def _assert_structure_exists(self):
        self.assertTrue(self._exists(self.category.content_filepath))
        self.assertTrue(self._exists(self.category.meta_filepath))

        self.assertTrue(self._exists(self.section.content_filepath))
        self.assertTrue(self._exists(self.section.meta_filepath))

        self.assertTrue(self._exists(self.article.content_filepath))
        self.assertTrue(self._exists(self.article.meta_filepath))
        self.assertTrue(self._exists(self.article.body_filepath))

    def _assert_article_deleted(self, zendesk_requests, translate_requests):
        self.assertFalse(self._exists(self.article.content_filepath))
        self.assertFalse(self._exists(self.article.meta_filepath))
        self.assertFalse(self._exists(self.article.body_filepath))
        translate_requests.delete.assert_any_call('https://webtranslateit.com/api/projects/test_key/files/3')
        translate_requests.delete.assert_any_call('https://webtranslateit.com/api/projects/test_key/files/4')

    def _assert_section_deleted(self, zendesk_requests, translate_requests):
        self.assertFalse(self._exists(self.section.content_filepath))
        self.assertFalse(self._exists(self.section.meta_filepath))
        translate_requests.delete.assert_any_call('https://webtranslateit.com/api/projects/test_key/files/2')

    def _assert_category_deleted(self, zendesk_requests, translate_requests):
        self.assertFalse(self._exists(self.section.content_filepath))
        self.assertFalse(self._exists(self.section.meta_filepath))
        translate_requests.delete.assert_any_call('https://webtranslateit.com/api/projects/test_key/files/1')

    @patch('translate.requests')
    @patch('zendesk.requests')
    def test_remove_article(self, zendesk_requests, translate_requests):
        self.args['path'] = self.article.content_filepath

        self._assert_structure_exists()
        self.task.execute(self.args)
        self._assert_article_deleted(zendesk_requests, translate_requests)
        zendesk_requests.delete.assert_any_call('https://test_company.com/api/v2/help_center/en-us/articles/3.json', verify=False, auth=('test_user', 'test_password'))


    @patch('translate.requests')
    @patch('zendesk.requests')
    def test_remove_section(self, zendesk_requests, translate_requests):
        self.args['path'] = self.section.path

        self._assert_structure_exists()
        self.task.execute(self.args)
        self._assert_section_deleted(zendesk_requests, translate_requests)
        self._assert_article_deleted(zendesk_requests, translate_requests)
        zendesk_requests.delete.assert_any_call('https://test_company.com/api/v2/help_center/en-us/sections/2.json', verify=False, auth=('test_user', 'test_password'))


    @patch('translate.requests')
    @patch('zendesk.requests')
    def test_remove_category(self, zendesk_requests, translate_requests):
        self.args['path'] = self.category.path

        self._assert_structure_exists()
        self.task.execute(self.args)
        self._assert_category_deleted(zendesk_requests, translate_requests)
        self._assert_section_deleted(zendesk_requests, translate_requests)
        self._assert_article_deleted(zendesk_requests, translate_requests)
        zendesk_requests.delete.assert_any_call('https://test_company.com/api/v2/help_center/en-us/categories/1.json', verify=False, auth=('test_user', 'test_password'))
