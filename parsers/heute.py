from baseparser import BaseParser
from BeautifulSoup import BeautifulSoup, Tag
import html2text


class HeuteParser(BaseParser):
    domains = ['heute.at']

    feeder_pat   = '^http://heute.at/(.*-[0-9]+)'
    feeder_pages = ['http://heute.at/']

    def _parse(self, html):
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES,
                             fromEncoding='utf-8')

        elt = soup.find('h1')
        self.title = elt.getText()

        self.byline = ''

        if len(soup.findAll('div', {'id': 'adapticker'}))>0:
            self.real_article = False
            return

        content = soup.findAll('div', {'class':lambda x: x and 'story_text' in x.split()})

        if len(content)==0:
            self.real_article = False
            return
        content = content[0]

        h = html2text.HTML2Text()

        self.body = h.handle(content.prettify().decode('utf-8'))
        self.body = self.body.split('&lt;!!&gt',1)[0]


        dcs = [x for x in soup.findAll('div', {'class':
            lambda x: x and 'published' in x})]
        dcs = [x.find('p') for x in dcs]
        dcs = [x.text for x in dcs if x]
        self.date = dcs[0].replace('Print','') if dcs else ''
