import os
import re
import json
import datetime
import itertools
import operator

from django.core.management.base import BaseCommand
from website.frontend.models import Article, Version
from django.db.models.aggregates import Count
from django.conf import settings

from optparse import make_option

import diff_match_patch

def has_erratum(old, new):
    dmp = diff_match_patch.diff_match_patch()
    dmp.Diff_Timeout = 3 # seconds; default of 1 is too little
    diff = dmp.diff_main(old, new)
    dmp.diff_cleanupSemantic(diff)
    chars_added   = '\n'.join([text for (sign, text) in diff if sign == 1])
    is_update = False
    for signifier in settings.CORRECTION_SIGNIFIERS:
        match = re.search(signifier, chars_added, re.IGNORECASE|re.MULTILINE)
        if match:
            is_update = match
    if is_update:
        remaining_chars = chars_added[is_update.start():]
        l = is_update.end()-is_update.start()
        remaining_lines = remaining_chars.split('\n')
        if len(remaining_lines[0])>l*5: # just one paragraph, or multiple?
            return remaining_lines[0]
        else:
            return remaining_chars
    else:
        return False

class Command(BaseCommand):
    help = ''' (Re)create JSON files for every day's changes. '''
    option_list = BaseCommand.option_list + (
        make_option('--all',
            action='store_true',
            default=False,
            help='(Re)create all diff jsons, not only today\'s'),
        )

    def handle(self, *args, **options):
        do_all = options['all']

        versions = Version.objects.all()

        if not do_all:
            versions = versions.filter(date__gte=datetime.date.today()-datetime.timedelta(days=1))

        versions = versions.order_by('date')

        versions_by_article = itertools.groupby(versions,
                key=lambda version: version.article_id)

        errata = []
        for article_id, versions_since_yesterday in versions_by_article:
            versions_since_yesterday = list(versions_since_yesterday)
            versioned_article = Article.objects.get(id=article_id)
            versions_ever = versioned_article.versions()
            versions_cur = versions_ever.filter(date__gte=versions_since_yesterday[0].date)
            if versions_cur.count()<2:
                continue
            for pair in zip(versions_cur[0:len(versions_cur)-1], versions_cur[1:]):
               err = has_erratum(pair[0].text(), pair[1].text())
               if err:
                   errata.append((versioned_article, pair, err,))

        errata_by_date = itertools.groupby(errata,
                key=lambda (a,p,e,): p[1].date.date()
        )
        for date, errata_on_day in errata_by_date:
            f = open(os.path.join(settings.WEBAPP_ROOT, '..', 'errata', date.isoformat()+'.json'), 'w')
            towrite = [{'url': versioned_article.url,
                       'time': pair[1].date.isoformat(),
                       'update': err,
                       'article_id': versioned_article.id,} for (versioned_article, pair, err,) in errata_on_day
                       ]
            print towrite
            json.dump(towrite, f)
            f.close()

        f2 = open(os.path.join(settings.WEBAPP_ROOT, '..', 'errata', 'sites.json'), 'w')
        json.dump(list(itertools.chain(*[x.domains for x in settings.PARSERS])), f2)
        f2.close()

