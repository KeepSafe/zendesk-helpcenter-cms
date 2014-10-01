from unittest import TestCase
from unittest.mock import create_autospec, mock_open, patch, MagicMock

from . import fixtures
from .. import translate


class TestWebTranslateItClient(TestCase):

    def setUp(self):
        self.req = create_autospec(translate.WebTranslateItRequest)
        self.client = translate.WebTranslateItClient(self.req)
        self.category = fixtures.simple_category()

    def test_create_happy_path(self):
        self.client._create_item = MagicMock()
        with patch('builtins.open', mock_open()):
            self.client.create([self.category])

        self.client._create_item.assert_any_call('category/__group__.json')
        self.client._create_item.assert_any_call('category/section/__group__.json')
        self.client._create_item.assert_any_call('category/section/en-US/article.json')
        self.client._create_item.assert_any_call('category/section/en-US/article.mkdown')

    def test_create_item_happy_path(self):
        with patch('builtins.open', mock_open()):
            self.client._create_item(self.category.content_filepath)

        self.assertEqual('files', self.req.post.call_args[0][0])
        self.assertEqual({'file': 'category/__group__.json', 'name': 'category/__group__.json'},
                         self.req.post.call_args[0][1])
        self.assertIn('file', self.req.post.call_args[0][2])

    def test_move_group(self):
        self.client._move_item = MagicMock()
        with patch('builtins.open', mock_open()):
            self.client.move(self.category, 'test/fixtures/articles.json')

        self.client._move_item.assert_called_with('category translate id', 'category/__group__.json')

    def test_move_article(self):
        self.client._move_item = MagicMock()
        with patch('builtins.open', mock_open()):
            self.client.move(self.category.sections[0].articles[0], 'test/fixtures/articles.json')

        self.client._move_item.assert_any_call('body translate id', 'category/section/en-US/article.mkdown')
        self.client._move_item.assert_any_call('article translate id', 'category/section/en-US/article.json')

    def test_move_item_happy_path(self):
        with patch('builtins.open', mock_open()):
            self.client._move_item('1', 'test/fixtures/articles.json')

        self.assertTrue(self.req.put.called)
        self.assertEqual('files/1/locales/en-US', self.req.put.call_args[0][0])
        self.assertEqual({'file': 'test/fixtures/articles.json', 'name': 'test/fixtures/articles.json'},
                         self.req.put.call_args[0][1])
        self.assertIn('file', self.req.put.call_args[0][2])

    def test_delete_happy_path(self):
        self.client.delete(self.category)

        self.assertEqual(1, self.req.delete.call_count)
        self.req.delete.assert_any_call('files/category translate id')

    def test_create_item_normalizes_path(self):
        with patch('builtins.open', mock_open()):
            self.client._create_item('test\\fixtures\\articles.json')

        self.assertEqual({'file': 'test/fixtures/articles.json', 'name': 'test/fixtures/articles.json'},
                         self.req.post.call_args[0][1])

    def test_move_item_normalizes_path(self):
        with patch('builtins.open', mock_open()):
            self.client._move_item('1', 'test\\fixtures\\articles.json')

        self.assertEqual({'file': 'test/fixtures/articles.json', 'name': 'test/fixtures/articles.json'},
                         self.req.put.call_args[0][1])
