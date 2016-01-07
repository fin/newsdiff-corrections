from baseparser import BaseParser
from BeautifulSoup import BeautifulSoup, Tag
import html2text
import re


class OrfParser(BaseParser):
    domains = ['orf.at']

    feeder_pat   = '^http://orf.at/stories/[0-9]{7}/'
    feeder_pages = ['http://orf.at/']

    def _parse(self, html):
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES,
                             fromEncoding='utf-8')

        self.meta = soup.findAll('meta')

        artikel = soup.find('div', {'class': re.compile(r'.*storyWrapper.*')})

        elt = artikel.find('h1')
        self.title = elt.getText()


        author = artikel.find('span', {"class":'articleauthor'})

        self.byline = author.getText() if author else ''

        content = artikel.find('div', id='ss-storyText')

        if not content:
            content = soup.find('div', {"class": 'storyText'})


        h = html2text.HTML2Text()

        storyMeta = artikel.find('div', {'class': re.compile(r'.*storyMeta.*')})
        if storyMeta:
            offscreen = storyMeta.find('span', {'class': 'offscreen'})
            if offscreen:
                offscreen.extract()
            date = storyMeta.find('p', {"class":'date'})
            self.date = '' if not date else date.getText()
            storyMeta.extract()
        else:
            self.date = soup.find('meta', {'name':'dc.date'})['content']

        if not content and not storyMeta:
            self.real_article = False
            return

        self.body = h.handle(content.prettify().decode('utf-8')).strip()

