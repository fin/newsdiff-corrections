from baseparser import BaseParser
from BeautifulSoup import BeautifulSoup, Tag
import html2text


class DiePresseParser(BaseParser):
    domains = ['diepresse.com']

    feeder_pat   = '^http://diepresse.com/.*/[0-9]{7}/.*'
    feeder_pages = ['http://diepresse.com/']

    def _parse(self, html):
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES,
                             fromEncoding='utf-8')

        self.meta = soup.findAll('meta')

        artikel = soup.find('div',role='main')

        if not artikel:
            self.real_article = False
            return

        more = artikel.find('div', {'class': "article_more"})
        if more:
            more.extract()

        elt = artikel.find('h1')
        if not elt:
            self.real_article = False
            return
        self.title = elt.getText()


        author = artikel.find('strong', {"class":'article__author'})

        if author:
            self.byline = author.getText()
        else:
            self.byline = ''


        lead = artikel.find('p', {'class': 'article__lead'})
        content = artikel.find('div', id='content-body')

        if not lead:
            self.real_article = False
            return


        if not content:
            content = soup.find('div', {"class": 'copytext'})
        if not content:
            content = soup.find('div', {"id": "content-main"})


        h = html2text.HTML2Text()

        date = artikel.find('span', {"class":'article__timestamp'})
        self.date = '' if not date else date.getText()

        self.body = (h.handle(lead.prettify().decode('utf-8')).strip()+'\n\n' if lead else '') + h.handle(content.prettify().decode('utf-8')).strip()


        if 'Wert zu wissen' in self.body: # ignore premium previews
            self.real_article = False
            return

        self.body = u'\n\n'.join(x for x in self.body.split('\n\n') if not x.startswith('Karte zur'))


