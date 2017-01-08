import os
import re
import json
import datetime
import itertools
import operator

from django.core.management.base import BaseCommand
from website.frontend.models import Article, Version, SEVERITY, SEVERITY_COMMENTS
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

        versions = Version.objects.filter(severity__gt=0)

        if not do_all:
            versions = versions.filter(date__gte=datetime.date.today()-datetime.timedelta(days=1))

        versions = versions.order_by('date')

        errata_by_date = itertools.groupby(versions,
                key=lambda x: x.date.date()
        )
        for date, errata_on_day in errata_by_date:
            print date
            f = open(os.path.join(settings.WEBAPP_ROOT, '..', 'errata', date.isoformat()+'.json'), 'w')
            towrite = [{'url': version.article.url,
                       'time': version.date.isoformat(),
                       'id': version.pk,
                       'update': version.severity_comment,
                       'severity': version.severity,
                       'title': version.title,
                       'article_id': version.article.id,} for version in errata_on_day
                       ]
            json.dump(towrite, f)
            f.close()

        f2 = open(os.path.join(settings.WEBAPP_ROOT, '..', 'errata', 'sites.json'), 'w')
        json.dump(list(itertools.chain(*[x.domains for x in settings.PARSERS])), f2)
        f2.close()

        f3 = open(os.path.join(settings.WEBAPP_ROOT, '..', 'errata', 'levels.json'), 'w')
        json.dump(sorted([{'level': k, 'value': v, 'comment': SEVERITY_COMMENTS.get(k,'')} for k,v in SEVERITY.iteritems()], key=lambda x: x['value']),
                f3)
        f3.close()

