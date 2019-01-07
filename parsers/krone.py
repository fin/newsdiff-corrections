from baseparser import BaseParser
from BeautifulSoup import BeautifulSoup, Tag
import html2text


class KroneParser(BaseParser):
    domains = ['www.krone.at', 'krone.at']

    feeder_pat   = '^https://www.krone.at/([0-9]+)'
    feeder_pages = ['https://www.krone.at/']

    def _parse(self, html):
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES,
                             fromEncoding='utf-8')

        if '/sport-mix/' in self.url:
            self.real_article = False
            return

        elt = soup.find('h1')
        self.title = elt.getText()

        self.byline = ''

        content = soup.findAll('div', {'class':lambda x: x and 'c_content' in x.split()})

        if len(content)==0:
            self.real_article = False
            return
        content = content[0]

        h = html2text.HTML2Text()

        self.body = h.handle(content.prettify().decode('utf-8'))


        dcs = [x for x in soup.findAll('div', {'class':
            lambda x: x and 'objekt_vorleger' in x})]
        dcs = [x.find('div', {'class': lambda x: x and 'c_time' in x})
                for x in dcs]
        dcs = [x for x in dcs if x]
        self.date = dcs[0].getText() if dcs else ''
