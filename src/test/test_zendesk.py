import os
import json
from unittest import TestCase
from unittest.mock import MagicMock, create_autospec

import zendesk
import filesystem
from . import fixtures


def load_fixture(name):
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fixtures', name + '.json')
    with open(path) as fp:
        return json.load(fp)


class TestFetcher(TestCase):

    def setUp(self):
        req = create_autospec(zendesk.ZendeskRequest)
        req.get_items.side_effect = lambda *c: load_fixture(c[0].zendesk_group)[c[0].zendesk_group]
        self.fetcher = zendesk.Fetcher(req)

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
        self.fs = create_autospec(filesystem.FilesystemClient)
        self.pusher = zendesk.Pusher(self.req, self.fs, 'dummy_path', False)
        self.category = fixtures.category_with_translations()

    def test_push_create(self):
        self.req.get_missing_locales = MagicMock(return_value=['pl'])
        self.pusher.push([self.category])

        self.req.post_translation.assert_any_call(self.category,
                                                  {'translation': {'title': 'dummy translation name', 'locale': 'pl',
                                                                   'body': 'dummy translation description'}})
        self.req.post_translation.assert_any_call(self.category.sections[0],
                                                  {'translation': {'title': 'dummy translation name',
                                                                   'body': 'dummy translation description',
                                                                   'locale': 'pl'}})
        self.req.post_translation.assert_any_call(self.category.sections[0].articles[0],
                                                  {'translation': {'locale': 'pl', 'title': 'dummy name',
                                                                   'body': '<p>dummy body</p>'}})

    def test_push_update(self):
        self.req.get_missing_locales = MagicMock(return_value=[])
        self.pusher._has_content_changed = MagicMock(return_value=True)
        self.pusher.push([self.category])

        self.req.put_translation.assert_any_call(self.category, 'pl', {
                                                 'translation': {'locale': 'pl', 'title': 'dummy translation name',
                                                                 'body': 'dummy translation description'}})
        self.req.put_translation.assert_any_call(self.category.sections[0], 'pl', {
                                                 'translation': {'locale': 'pl', 'title': 'dummy translation name',
                                                                 'body': 'dummy translation description'}})
        self.req.put_translation.assert_any_call(self.category.sections[0].articles[0], 'pl', {
                                                 'translation': {'locale': 'pl', 'title': 'dummy name',
                                                                 'body': '<p>dummy body</p>'}})
