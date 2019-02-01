# -*- coding: utf-8 -*-
from baseparser import BaseParser
from BeautifulSoup import BeautifulSoup, Tag
import html2text


class DerStandardParser(BaseParser):
    domains = ['derstandard.at', 'diestandard.at', 'dastandard.at']

    feeder_pat   = '^https://derstandard.at/(Jetzt|[0-9]+)/'
    feeder_pages = ['https://derstandard.at/']

    def _parse(self, html):
        soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES,
                             fromEncoding='utf-8')

        for x in soup.findAll('a'):
            if 'Aus den Foren' in x.getText():
                self.real_article = False
                return

        self.meta = soup.findAll('meta')
        elt = soup.find('h1')
        self.title = elt.getText()

        if u'tägliche Reise' in self.title:
            self.real_article = False
            return


        info = soup.find('h6', {"class": "info"})
        author = info.find('span', {"class":'author'})
        if author:
            self.byline = author.getText()
        else:
            self.byline = ''

        content = soup.find('div', id='content-main')

        if not content:
            content = soup.find('div', {"class": 'copytext'})

        if not content:
            content = soup.find('div', {"id": "content-main"})


        h = html2text.HTML2Text()

        self.body = h.handle(content.prettify().decode('utf-8'))

        self.date = info.find('span', {"class":'date'}).getText()
