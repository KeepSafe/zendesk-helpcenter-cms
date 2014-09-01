# from unittest.mock import MagicMock, patch
# from unittest import TestCase
# import items
# import utils


# class TestAbstractItem(TestCase):

#     def setUp(self):
#         with patch('os.makedirs'):
#             self.item = items.AbstractItem('test_path')
#         self.item._meta_filename = 'dummy meta'
#         self.item._content_filename = 'dummy content'

#     def test_zendesk_id_returns_none_if_missing(self):
#         self.item.meta_repo.read = MagicMock(return_value=None)
#         self.assertIsNone(self.item.zendesk_id)

#     def test_zendesk_id_happy_path(self):
#         self.item.meta_repo.read = MagicMock(return_value={items.AbstractItem.ZENDESK_KEY: '1'})
#         self.assertEqual(self.item.zendesk_id, '1')

#     def test_translate_ids_returns_empty_list_if_missing(self):
#         self.item.meta_repo.read = MagicMock(return_value=None)
#         self.assertEqual(self.item.translate_ids, [])

#     def test_translate_ids_happy_path(self):
#         self.item.meta_repo.read = MagicMock(return_value={items.AbstractItem.TRANSLATE_KEY: ['1', '2']})
#         self.assertEqual(self.item.translate_ids, ['1', '2'])

#     def test_fixme_happy_path(self):
#         self.item.content_repo.save = MagicMock()
#         self.item.fixme('dummy content')
#         self.assertTrue(self.item.content_repo.save.called)


# class TestGroup(TestCase):

#     def setUp(self):
#         with patch('os.makedirs'):
#             self.parent = items.Group('dummy parent')
#             self.child = items.Group('dummy child', self.parent)

#     def test_children_articles_happy_path(self):
#         with patch('os.listdir') as mock_listdir, patch('os.path.isfile') as mock_isfile:
#             mock_listdir.return_value = ['test article.md', 'some file']
#             mock_isfile.return_value = True

#             children = self.child.children

#         self.assertEqual(len(children), 1)
#         self.assertEqual(children[0].name, 'test article')

#     def test_children_articles_skip_files_with_more_then_one_dot(self):
#         with patch('os.listdir') as mock_listdir, patch('os.path.isfile') as mock_isfile:
#             mock_listdir.return_value = ['some.file.md']
#             mock_isfile.return_value = True

#             children = self.child.children

#         self.assertEqual(len(children), 0)

#     def test_children_subgroups_happy_path(self):
#         with patch('os.listdir') as mock_listdir, patch('os.path.isdir') as mock_isdir:
#             mock_listdir.return_value = ['test group']
#             mock_isdir.return_value = True

#             children = self.parent.children

#         self.assertEqual(len(children), 1)

#     def _test_translations(self, return_value, expected):
#         self.child._content_filename = 'dummy file.json'
#         with patch('os.listdir') as mock_listdir:
#             mock_listdir.return_value = return_value

#             translations = self.child.translations

#         self.assertDictEqual(translations, expected)

#     def test_translations_happy_path(self):
#         self._test_translations(['dummy file.pl.json'], {'pl': 'dummy child/dummy file.pl.json'})

#     def test_translations_use_default_locale_if_missing(self):
#         self._test_translations(['dummy file.json'], {utils.DEFAULT_LOCALE: 'dummy child/dummy file.json'})

#     def test_translations_ignore_files_with_different_names(self):
#         self._test_translations(
#             ['dummy file.pl.json', 'dummy file.pl.js', 'dummy_file.pl.json'], {'pl': 'dummy child/dummy file.pl.json'})


# class TestArticle(TestCase):
#     def setUp(self):
#         with patch('os.makedirs'):
#             self.article = items.Article('dummy path', 'dummy name')

#     def test_translations_happy_path(self):
#         self.article._content_filename = 'dummy content file.json'
#         self.article.name = 'dummy body file'
#         with patch('os.listdir') as mock_listdir:
#             mock_listdir.return_value = ['dummy content file.json', 'dummy body file.md']

#             translations = self.article.translations

#         expected = {utils.DEFAULT_LOCALE: ['dummy path/dummy content file.json', 'dummy path/dummy body file.md']}
#         self.assertDictEqual(translations, expected)
