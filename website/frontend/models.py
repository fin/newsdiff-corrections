import re
import subprocess
import os
from datetime import datetime, timedelta

import json
from django.db import models, IntegrityError
from django.conf import settings
import diff_match_patch

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(THIS_DIR))
GIT_DIR = ROOT_DIR+'/articles/'

GIT_PROGRAM = 'git'

from website.frontend.management.commands.parsers import parser_dict

def strip_prefix(string, prefix):
    if string.startswith(prefix):
        string = string[len(prefix):]
    return string


PublicationDict = dict([(k,v.__name__.replace('Parser', ''),) for k,v in parser_dict.iteritems()])

ancient = datetime(1901, 1, 1)

SEVERITY = {
  "BORING": 0,
  "MINIMAL": 10,
  "LOW": 25,
  "MODERATE": 50,
  "HIGH": 75,
  "OFFICIAL": 99,
}

SEVERITY_COMMENTS = {
  "MINIMAL": 'At least slight changes were made',
  "LOW": 'At least a fifth of the length of the article was changed',
  "MODERATE": 'At least half of the article was changed',
  "OFFICIAL": 'Explicit Erratum or Update statement',
}

# Create your models here.
class Article(models.Model):
    class Meta:
        db_table = 'articles'

    url = models.CharField(max_length=255, blank=False, unique=True,
                           db_index=True)
    initial_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(default=ancient)
    last_check = models.DateTimeField(default=ancient)
    git_dir = models.CharField(max_length=255, blank=False, default='old')

    @property
    def full_git_dir(self):
        return GIT_DIR + self.git_dir

    def filename(self):
        ans = self.url.rstrip('/')
        if ans.startswith('http://'):
            return ans[len('http://'):]
        elif ans.startswith('https://'):
            # Terrible hack for backwards compatibility from when https was stored incorrectly,
            # perpetuating the problem
            return 'https:/' + ans[len('https://'):]
        raise ValueError("Unknown file type '%s'" % self.url)

    def publication(self):
        return PublicationDict.get(self.url.split('/')[2])

    def versions(self):
        return self.version_set.filter(boring=False).order_by('date')

    def latest_version(self):
        return self.versions().latest()

    def first_version(self):
        return self.versions()[0]

    def minutes_since_update(self):
        delta = datetime.now() - max(self.last_update, self.initial_date)
        return delta.seconds // 60 + 24*60*delta.days

    def minutes_since_check(self):
        delta = datetime.now() - self.last_check
        return delta.seconds // 60 + 24*60*delta.days

class VersionManager(models.Manager):
    def get_query_set(self):
        return super(VersionManager, self).get_query_set().defer('diff_details_json', 'diff_json')


class Version(models.Model):
    class Meta:
        db_table = 'version'
        get_latest_by = 'date'

    article = models.ForeignKey('Article', null=False)
    v = models.CharField(max_length=255, blank=False)
    title = models.CharField(max_length=255, blank=False)
    byline = models.CharField(max_length=255,blank=False)
    date = models.DateTimeField(blank=False)
    boring = models.BooleanField(blank=False, default=False)
    diff_json = models.CharField(max_length=255, null=True)
    diff_details_json = models.TextField(null=True)
    severity = models.IntegerField(null=True)
    severity_comment = models.TextField(null=True)

    objects = VersionManager()

    def text(self):
        try:
            return subprocess.check_output([GIT_PROGRAM, 'show',
                                            self.v+':'+self.article.filename()],
                                           cwd=self.article.full_git_dir)
        except subprocess.CalledProcessError as e:
            return None

    def get_diff_info(self):
        if self.diff_json is None:
            return {}
        return json.loads(self.diff_json)
    def set_diff_info(self, val=None):
        if val is None:
            self.diff_json = None
        else:
            self.diff_json = json.dumps(val)
    diff_info = property(get_diff_info, set_diff_info)

    def previous_version(self):
        vs = self.article.version_set.filter(date__lt=self.date).order_by('-date')
        if vs:
            return vs[0]
        return None

    def diff_details(self):
        if self.diff_details_json is not None:
            return json.loads(self.diff_details_json)

        pv = self.previous_version()


        if pv is None:
            diff_details = []
        else:
            old = pv.text()
            cur = self.text()
            if old is None or cur is None:
                diff_details = []
            else:
                dmp = diff_match_patch.diff_match_patch()
                dmp.Diff_Timeout = 3 # seconds; default of 1 is too little
                diff = dmp.diff_main(old.decode('utf-8'), cur.decode('utf-8'))
                dmp.diff_cleanupSemantic(diff)
                diff_details = diff

        self.diff_details_json = json.dumps(diff_details, ensure_ascii=False)
        self.save()

        return self.diff_details()

    @classmethod
    def diff_is_erratum(cls, diff):
        chars_added   = '\n'.join([text for (sign, text) in diff if sign == 1])
        is_update = False
        for signifier in settings.CORRECTION_SIGNIFIERS:
            match = re.search(signifier, chars_added, re.IGNORECASE|re.MULTILINE)
            if match:
                is_update = match
                remaining_chars = chars_added[is_update.start():]
                l = is_update.end()-is_update.start()
                remaining_lines = remaining_chars.split('\n')
                if len(remaining_lines[0])>l*5: # just one paragraph, or multiple?
                    return remaining_lines[0]
                else:
                    return remaining_chars
        return False

    def update_severity(self, save=True):
        severity = 0
        severity_comment = None

        if self.diff_info:
            chars_changed = self.diff_info['chars_added']+self.diff_info['chars_removed']
            if chars_changed>0:
                severity = SEVERITY["MINIMAL"]
                severity_comment = SEVERITY_COMMENTS["MINIMAL"]

            if chars_changed>len(self.text())/5:
                severity = SEVERITY["LOW"]
                severity_comment = SEVERITY_COMMENTS["LOW"]

            if chars_changed>len(self.text())/2:
                severity = SEVERITY["MODERATE"]
                severity_comment = SEVERITY_COMMENTS["MODERATE"]


        # MISSING: whole-paragraph add/delete, etc



        erratum = type(self).diff_is_erratum(self.diff_details())
        if erratum and erratum.strip():
            severity = SEVERITY["OFFICIAL"]
            severity_comment = erratum

        if severity != self.severity or severity_comment != self.severity_comment:
            self.severity = severity
            self.severity_comment = severity_comment
            if save:
                self.save()

        return self.severity, self.severity_comment


class Upvote(models.Model):
    class Meta:
        db_table = 'upvotes'

    article_id = models.IntegerField(blank=False)
    diff_v1 = models.CharField(max_length=255, blank=False)
    diff_v2 = models.CharField(max_length=255, blank=False)
    creation_time = models.DateTimeField(blank=False)
    upvoter_ip = models.CharField(max_length=255)


# subprocess.check_output appeared in python 2.7.
# backport it to 2.6
def check_output(*popenargs, **kwargs):
    r"""Run command with arguments and return its output as a byte string.

    If the exit code was non-zero it raises a CalledProcessError.  The
    CalledProcessError object will have the return code in the returncode
    attribute and output in the output attribute.

    The arguments are the same as for the Popen constructor.  Example:

    >>> check_output(["ls", "-l", "/dev/null"])
    'crw-rw-rw- 1 root root 1, 3 Oct 18  2007 /dev/null\n'

    The stdout argument is not allowed as it is used internally.
    To capture standard error in the result, use stderr=STDOUT.

    >>> check_output(["/bin/sh", "-c",
    ...               "ls -l non_existent_file ; exit 0"],
    ...              stderr=STDOUT)
    'ls: non_existent_file: No such file or directory\n'
    """
    from subprocess import PIPE, CalledProcessError, Popen
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = Popen(stdout=PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise CalledProcessError(retcode, cmd, output=output)
    return output

if not hasattr(subprocess, 'check_output'):
    subprocess.check_output = check_output
