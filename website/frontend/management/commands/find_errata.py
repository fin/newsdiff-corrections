from django.core.management.base import BaseCommand
from website.frontend.models import Article, Version
from django.db.models.aggregates import Count
from django.conf import settings

import re

import diff_match_patch

def has_erratum(old, new):
    dmp = diff_match_patch.diff_match_patch()
    dmp.Diff_Timeout = 3 # seconds; default of 1 is too little
    diff = dmp.diff_main(old, new)
    dmp.diff_cleanupSemantic(diff)
    chars_added   = '\n'.join([text for (sign, text) in diff if sign == 1]).lower()
    is_update = False
    for signifier in settings.CORRECTION_SIGNIFIERS:
        match = re.search(signifier, chars_added, re.MULTILINE)
        if match:
            is_update = match
    if is_update:
        remaining_chars = chars_added[is_update.start():]
        l = is_update.end()-is_update.start()
        remaining_lines = remaining_chars.split('\n')
        if len(remaining_lines[0])>l*5:
            return remaining_lines[0]
        else:
            return remaining_chars
    else:
        return False

class Command(BaseCommand):
    help = ''' do the thing '''

    def handle(self, *args, **options):
        versioned_articles = Article.objects.all()\
            .annotate(count_versions=Count('version'))\
            .filter(count_versions__gt=1)
        for versioned_article in versioned_articles:
            versions = versioned_article.versions()
            for pair in zip(versions[0:len(versions)-1], versions[1:]):
               err = has_erratum(pair[0].text(), pair[1].text())
               if err:
                   print err
