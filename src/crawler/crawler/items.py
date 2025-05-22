import scrapy


class LoanItem(scrapy.Item):
    """Item for storing loan and crawled content information"""
    work_order = scrapy.Field()
    make = scrapy.Field()
    model = scrapy.Field()
    source = scrapy.Field()
    url = scrapy.Field()
    content = scrapy.Field()
    title = scrapy.Field()
    publication_date = scrapy.Field()
    content_type = scrapy.Field()  # 'article' or 'video'
    crawl_date = scrapy.Field()
    crawl_level = scrapy.Field()  # 1, 2, or 3 (which crawling level was used)
    error = scrapy.Field() 