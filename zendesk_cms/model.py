from collections import namedtuple

Handler = namedtuple('ItemHandler', ['categories', 'sections', 'articles'])

Category = namedtuple('Category', ['path', 'content', 'meta'])
Section = namedtuple('Section', Category._fields + ('category',))
Article = namedtuple('Article', Category._fields + ('section',))
