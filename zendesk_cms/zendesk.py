"""

"""

import requests
from functools import partial
from collections import namedtuple

from .model import Handler


ZENDESK_URL = 'https://{company_domain}/api/v2/help_center/{locale}/{path}'

CATEGORIES_PATH = 'categories.json'
CATEGORY_PATH = 'categories/{}.json'
SECTIONS_PATH = 'categories/{}/sections.json'
SECTION_PATH = 'sections/{}.json'
ARTICLES_PATH = 'sections/{}/articles.json'
ARTICLE_PATH = 'articles/{}.json'

CATEGORY_NAME = 'category'
CATEGORIES_NAME = 'categories'
SECTION_NAME = 'section'
SECTIONS_NAME = 'sections'
ARTICLE_NAME = 'article'
ARTICLES_NAME = 'articles'

Req = namedtuple('Req', ['all', 'one', 'new', 'update', 'delete'])


def DefaultReq():
    return Req(
        requests.get,
        requests.get,
        requests.post,
        requests.put,
        requests.delete,
    )


def AuthReq(req, user, password):
    return Req(
        partial(req.all, auth=(user, password)),
        partial(req.one, auth=(user, password)),
        partial(req.new, auth=(user, password)),
        partial(req.update, auth=(user, password)),
        partial(req.delete, auth=(user, password))
    )


def JsonReq(req):
    def parse_response(res):
        #TODO handle errors
        return res.json()
    return Req(
        lambda **kwargs: parse_response(req.all(**kwargs)),
        lambda **kwargs: parse_response(req.one(**kwargs)),
        lambda **kwargs: parse_response(req.new(**kwargs)),
        lambda **kwargs: parse_response(req.update(**kwargs)),
        lambda **kwargs: parse_response(req.delete(**kwargs))
    )


def PageExtractingReq(req):
    def make_req(fun, group_name, **kwargs):
        res = fun(**kwargs)
        items = res.get(group_name, [])
        return res, items

    def page(fun, **kwargs):
        res, items = make_req(fun, **kwargs)
        idx = 0
        while items and idx < 100:
            idx = idx + 1
            for item in items:
                yield item
            if res['next_page']:
                kwargs['url'] = res['next_page']
                res, items = make_req(fun, **kwargs)
            else:
                items = []
        if idx == 100:
            #TODO log error
            pass


    return Req(
        partial(page, fun=req.all),
        lambda item_name, group_name, **kwargs: req.one(**kwargs).get(item_name, {}),
        lambda item_name, group_name, **kwargs: req.new(**kwargs).get(item_name, {}),
        lambda item_name, group_name, **kwargs: req.update(**kwargs).get(item_name, {}),
        lambda item_name, group_name, **kwargs: req.delete(**kwargs).get(item_name, {}),
    )


def ZendeskReq(req, url, company_domain):
    path_url = partial(url.format, company_domain=company_domain)
    return Req(
        lambda path, locale, **kwargs: req.all(url=path_url(path=path, locale=locale), **kwargs),
        lambda path, locale, **kwargs: req.one(url=path_url(path=path, locale=locale), **kwargs),
        lambda path, locale, **kwargs: req.new(url=path_url(path=path, locale=locale), **kwargs),
        lambda path, locale, **kwargs: req.update(url=path_url(path=path, locale=locale), **kwargs),
        lambda path, locale, **kwargs: req.delete(url=path_url(path=path, locale=locale), **kwargs)
    )


def TranslationReq(req, locale):
    return Req(
        partial(req.all, locale=locale),
        partial(req.one, locale=locale),
        partial(req.new, locale=locale),
        partial(req.update, locale=locale),
        partial(req.delete, locale=locale)
    )


def CategoryReq(req):
    return Req(
        partial(req.all, path=CATEGORIES_PATH, item_name=CATEGORY_NAME, group_name=CATEGORIES_NAME),
        lambda category_id, **kwargs: req.one(path=CATEGORY_PATH.format(category_id), item_name=CATEGORY_NAME, group_name=CATEGORIES_NAME, **kwargs),
        lambda data, **kwargs: req.new(path=CATEGORIES_PATH, data=data, item_name=CATEGORY_NAME, group_name=CATEGORIES_NAME, **kwargs),
        lambda category_id, data, **kwargs: req.update(path=CATEGORY_PATH.format(category_id), data=data, item_name=CATEGORY_NAME, group_name=CATEGORIES_NAME, **kwargs),
        lambda category_id, **kwargs: req.delete(path=CATEGORY_PATH.format(category_id), item_name=CATEGORY_NAME, group_name=CATEGORIES_NAME, **kwargs)
    )


def SectionReq(req):
    return Req(
        lambda category_id, **kwargs: req.all(path=SECTIONS_PATH.format(category_id), item_name=SECTION_NAME, group_name=SECTIONS_NAME, **kwargs),
        lambda section_id, **kwargs: req.one(path=SECTION_PATH.format(section_id), item_name=SECTION_NAME, group_name=SECTIONS_NAME, **kwargs),
        lambda category_id, data, **kwargs: req.new(path=SECTIONS_PATH.format(category_id), data=data, item_name=SECTION_NAME, group_name=SECTIONS_NAME, **kwargs),
        lambda section_id, data, **kwargs: req.update(path=SECTION_PATH.format(section_id), data=data, item_name=SECTION_NAME, group_name=SECTIONS_NAME, **kwargs),
        lambda section_id, **kwargs: req.delete(path=SECTION_PATH.format(section_id), item_name=SECTION_NAME, group_name=SECTIONS_NAME, **kwargs)
    )


def ArticleReq(req):
    return Req(
        lambda section_id, **kwargs: req.all(path=ARTICLES_PATH.format(section_id), item_name=ARTICLE_NAME, group_name=ARTICLES_NAME, **kwargs),
        lambda article_id, **kwargs: req.one(path=ARTICLE_PATH.format(article_id), item_name=ARTICLE_NAME, group_name=ARTICLES_NAME, **kwargs),
        lambda section_id, data, **kwargs: req.new(path=ARTICLES_PATH.format(section_id), data=data, item_name=ARTICLE_NAME, group_name=ARTICLES_NAME, **kwargs),
        lambda article_id, data, **kwargs: req.update(path=ARTICLE_PATH.format(article_id), data=data, item_name=ARTICLE_NAME, group_name=ARTICLES_NAME, **kwargs),
        lambda article_id, **kwargs: req.delete(path=ARTICLE_PATH.format(article_id), item_name=ARTICLE_NAME, group_name=ARTICLES_NAME, **kwargs)
    )


def item_req(config, base_req=DefaultReq()):
    auth_req = AuthReq(base_req, config['user'], config['password'])
    json_req = JsonReq(auth_req)
    paging_req = PageExtractingReq(json_req)
    zendesk_req = ZendeskReq(paging_req, ZENDESK_URL, config['company_domain'])
    category_req = CategoryReq(zendesk_req)
    section_req = SectionReq(zendesk_req)
    article_req = ArticleReq(zendesk_req)

    return Handler(
        TranslationReq(category_req, config['locale']),
        TranslationReq(section_req, config['locale']),
        TranslationReq(article_req, config['locale']),
    )


def items(item_req):
    categories = item_req.categories.all()
    for category in categories:
        yield category
        sections = item_req.sections.all(category['id'])
        for section in sections:
            yield section
            articles = item_req.articles.all(section['id'])
            for article in articles:
                yield article
