from ... import model


def simple_category():
    category = model.Category('category', 'category desc', 'category')
    category.meta = {'id': 'category id', 'webtranslateit_ids': ['category translate id']}
    section = model.Section(category, 'section', 'section desc', 'section')
    section.meta = {'id': 'section id', 'webtranslateit_ids': ['section translate id']}
    article = model.Article(section, 'article', 'body', 'article')
    article.meta = {'id': 'article id', 'webtranslateit_ids': ['body translate id', 'article translate id']}
    category.sections.append(section)
    section.articles.append(article)
    return category


def category_with_translations():
    category = simple_category()
    group_translation = model.GroupTranslation('pl', 'dummy translation name', 'dummy translation description')
    category.translations.append(group_translation)
    category.sections[0].translations.append(group_translation)
    article_translation = model.ArticleTranslation('pl', 'dummy name', 'dummy body')
    category.sections[0].articles[0].translations.append(article_translation)
    return category
