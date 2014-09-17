import os
import json
from unittest import TestCase
from unittest.mock import MagicMock, create_autospec

import zendesk
from . import fixtures


def load_fixture(name):
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fixtures', name + '.json')
    with open(path) as fp:
        return json.load(fp)


class TestFetcher(TestCase):

    def setUp(self):
        req = create_autospec(zendesk.ZendeskRequest)
        self.fetcher = zendesk.Fetcher(req)
        self.fetcher._fetch_categories = MagicMock(return_value=load_fixture('categories')['categories'])
        self.fetcher._fetch_sections = MagicMock(return_value=load_fixture('sections')['sections'])
        self.fetcher._fetch_articles = MagicMock(return_value=load_fixture('articles')['articles'])

    def test_fetch_happy_path(self):
        categories = self.fetcher.fetch()

        self.assertEqual(1, len(categories))
        self.assertEqual(1, len(categories[0].sections))
        self.assertEqual(1, len(categories[0].sections[0].articles))

    def test_fetch_resolves_category(self):
        categories = self.fetcher.fetch()

        category = categories[0]
        self.assertEqual('test category', category.name)
        self.assertEqual('test category description', category.description)

    def test_fetch_resolves_section(self):
        categories = self.fetcher.fetch()

        section = categories[0].sections[0]
        self.assertEqual('test section', section.name)
        self.assertEqual('test section description', section.description)

    def test_fetch_resolves_article(self):
        categories = self.fetcher.fetch()

        article = categories[0].sections[0].articles[0]
        self.assertEqual('test article', article.name)
        self.assertEqual('### title\n\nbody\n\n', article.body)
        self.assertFalse(hasattr(article, 'description'))


class TestPusher(TestCase):

    def setUp(self):
        self.req = create_autospec(zendesk.ZendeskRequest)
        self.pusher = zendesk.Pusher(self.req)
        self.category = fixtures.category_with_translations()

    def test_push_create(self):
        self.req.get = MagicMock(return_value={'locales': ['pl']})
        self.pusher.push([self.category])

        self.req.post.assert_any_call('categories/category id/translations.json',
                                      {'title': 'dummy translation name', 'body': 'dummy translation description',
                                       'locale': 'pl'})
        self.req.post.assert_any_call('sections/section id/translations.json',
                                      {'title': 'dummy translation name', 'body': 'dummy translation description',
                                       'locale': 'pl'})
        self.req.post.assert_any_call('articles/article id/translations.json',
                                      {'locale': 'pl', 'title': 'dummy name', 'body': 'dummy body'})

    def test_push_update(self):
        self.req.get = MagicMock(return_value={'locales': []})
        self.pusher.push([self.category])

        self.req.put.assert_any_call('categories/category id/translations/pl.json',
                                     {'title': 'dummy translation name', 'body': 'dummy translation description',
                                      'locale': 'pl'})
        self.req.put.assert_any_call('sections/section id/translations/pl.json',
                                     {'title': 'dummy translation name', 'body': 'dummy translation description',
                                      'locale': 'pl'})
        self.req.put.assert_any_call('articles/article id/translations/pl.json',
                                     {'locale': 'pl', 'title': 'dummy name', 'body': 'dummy body'})
