from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from w3lib.url import url_query_cleaner


def process_links(links):
    for link in links:
        link.url = url_query_cleaner(link.url)
        yield link


class SEOSpider(CrawlSpider):
    name = 'seo_spider'
    handle_httpstatus_list = [200, 301, 302, 303, 307, 400, 401, 403, 404, 500]

    rules = (
        # Rule(
        #     LinkExtractor(
        #         allow_domains=config['allow_domains'],
        #     ),
        #     callback='parse_local',
        #     follow=True,
        # ),
        # Rule(
        #     LinkExtractor(),
        #     callback='parse_external',
        # ),
        Rule(
            LinkExtractor(),
            callback='parse_local',
            follow=True,
            process_links=process_links,
        ),
    )

    def __init__(self, url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [url]
        self.allowed_domains = [url.split('/')[2]]

    def parse_local(self, response):
        content_type = response.headers.get('Content-Type', b'').decode("utf-8")

        if response.status != 200:
            return {
                'url': response.url,
                'status': response.status,
                'type': 'local',
                'content_type': content_type,
                'title': '',
                'description': '',
                'canonical': '',
                'og_title': '',
                'og_description': '',
                'og_image': '',
                'og_url': '',
                'h1': '',
            }

        if "text/html" not in content_type:
            return {
                'url': response.url,
                'status': response.status,
                'type': 'local',
                'content_type': content_type,
                'title': '',
                'description': '',
                'canonical': '',
                'og_title': '',
                'og_description': '',
                'og_image': '',
                'og_url': '',
                'h1': '',
            }

        return {
            'url': response.url,
            'status': response.status,
            'type': 'local',
            'content_type': content_type,
            'title': response.xpath('normalize-space(//title)').get(),
            'description': response.xpath('normalize-space(//meta[@name="description"]/@content)').get(),
            'canonical': response.xpath('normalize-space(//link[@rel="canonical"]/@href)').get(),
            'og_title': response.xpath('normalize-space(//meta[@property="og:title"]/@content)').get(),
            'og_description': response.xpath('normalize-space(//meta[@property="og:description"]/@content)').get(),
            'og_image': response.xpath('normalize-space(//meta[@property="og:image"]/@content)').get(),
            'og_url': response.xpath('normalize-space(//meta[@property="og:url"]/@content)').get(),
            'h1': response.xpath('normalize-space(//h1)').get(),
        }

    # def parse_external(self, response):
    #     if response.status != 200:
    #         return {
    #             'url': response.url,
    #             'status': response.status,
    #             'type': 'external',
    #         }

    #     return {
    #         'url': response.url,
    #         'status': response.status,
    #         'type': 'external',
    #         'content_type': response.headers.get('Content-Type', b'').decode("utf-8"),
    #     }
