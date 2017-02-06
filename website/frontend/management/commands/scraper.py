#!/usr/bin/python

from datetime import datetime
import errno
from frontend import models
import httplib
import logging
import os
import subprocess
import sys
import time
import traceback
import urllib2
import json
import collections
import concurrent.futures
import itertools

import diff_match_patch

import parsers
from parsers.baseparser import canonicalize, formatter, logger

GIT_PROGRAM = 'git'

from django.core.management.base import BaseCommand
from optparse import make_option

def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--update',
            action='store_true',
            default=False,
            help='DEPRECATED; this is the default'),
        make_option('--all',
            action='store_true',
            default=False,
            help='Update _all_ stored articles'),
        )
    help = '''Scrape websites.

By default, scan front pages for new articles, and scan
existing and new articles to archive their current contents.

Articles that haven't changed in a while are skipped if we've
scanned them recently, unless --all is passed.
'''.strip()

    def handle(self, *args, **options):
        import signal

        def handle_pdb(sig, frame):
            import pdb
            pdb.Pdb().set_trace(frame)
        signal.signal(signal.SIGUSR1, handle_pdb)
        print(os.getpid())

        ch = logging.FileHandler('/tmp/newsdiffs_logging', mode='w')
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        ch = logging.FileHandler('/tmp/newsdiffs_logging_errs', mode='a')
        ch.setLevel(logging.WARNING)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        for repo in all_git_repos():
            cleanup_git_repo(repo)

        todays_repo = get_and_make_git_repo()

        update_articles(todays_repo)
        update_versions(todays_repo, options['all'])

# Begin utility functions

# subprocess.check_output appeared in python 2.7.
# Linerva only has 2.6
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
        err = CalledProcessError(retcode, cmd)
        err.output = output
        raise err
    return output

if not hasattr(subprocess, 'check_output'):
    subprocess.check_output = check_output

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise

def canonicalize_url(url):
    return url.split('?')[0].split('#')[0].strip()

class IndexLockError(OSError):
    pass

def make_new_git_repo(full_dir):
    mkdir_p(full_dir)
    tmpfile = os.path.join(full_dir, 'x')
    open(tmpfile, 'w').close()

    try:
        subprocess.check_output([GIT_PROGRAM, 'init',], cwd=full_dir)
        subprocess.check_output([GIT_PROGRAM, 'add', tmpfile], cwd=full_dir)
        subprocess.check_output([GIT_PROGRAM, 'commit', '-m', 'Initial commit'],
                                cwd=full_dir)
    except subprocess.CalledProcessError as e:
        raise

def get_and_make_git_repo():
    result = time.strftime('%Y-%m', time.localtime())
    full_path = models.GIT_DIR+result
    if not os.path.exists(full_path+'/.git'):
        make_new_git_repo(full_path)
    return result

def all_git_repos():
    import glob
    return glob.glob(models.GIT_DIR+'*')

def run_git_command(command, git_dir, max_timeout=15):
    """Run a git command like ['show', filename] and return the output.

    First, wait up to max_timeout seconds for the index.lock file to go away.
    If the index.lock file remains, raise an IndexLockError.

    Still have a race condition if two programs run this at the same time.
    """
    end_time = time.time() + max_timeout
    delay = 0.1
    lock_file = os.path.join(git_dir, '.git/index.lock')
    while os.path.exists(lock_file):
        if time.time() < end_time - delay:
            time.sleep(delay)
        else:
            raise IndexLockError('Git index.lock file exists for %s seconds'
                                 % max_timeout)
    output =  subprocess.check_output([GIT_PROGRAM] + command,
                                      cwd=git_dir,
                                      stderr=subprocess.STDOUT)
    return output

def get_all_article_urls():
    ans = set()
    for parser in parsers.parsers:
        logger.info('Looking up %s' % parser.domains)
        urls = parser.feed_urls()
        ans = ans.union(map(canonicalize_url, urls))
    return ans

CHARSET_LIST = """EUC-JP GB2312 EUC-KR Big5 SHIFT_JIS windows-1252
IBM855
IBM866
ISO-8859-2
ISO-8859-5
ISO-8859-7
KOI8-R
MacCyrillic
TIS-620
windows-1250
windows-1251
windows-1253
windows-1255""".split()
def is_boring(old, new):
    oldu = canonicalize(old.decode('utf8'))
    newu = canonicalize(new.decode('utf8'))

    def extra_canonical(s):
        """Ignore changes in whitespace or the date line"""
        nondate_portion = s.split('\n', 1)[1]
        return nondate_portion.split()

    if extra_canonical(oldu) == extra_canonical(newu):
        return True

    for charset in CHARSET_LIST:
        try:
            if oldu.encode(charset) == new:
                logger.debug('Boring!')
                return True
        except UnicodeEncodeError:
            pass
    return False

def get_diff(old, new):
    dmp = diff_match_patch.diff_match_patch()
    dmp.Diff_Timeout = 3 # seconds; default of 1 is too little
    diff = dmp.diff_main(old, new)
    dmp.diff_cleanupSemantic(diff)
    return diff

def get_diff_info(diff):
    if diff is None:
        return None
    chars_added   = sum(len(text) for (sign, text) in diff if sign == 1)
    chars_removed = sum(len(text) for (sign, text) in diff if sign == -1)
    return dict(chars_added=chars_added, chars_removed=chars_removed)

def add_to_git_repo(data, filename, article):
    start_time = time.time()

    #Don't use full path because it can exceed the maximum filename length
    #full_path = os.path.join(models.GIT_DIR, filename)
    os.chdir(article.full_git_dir)
    mkdir_p(os.path.dirname(filename))

    boring = False
    diff = None

    try:
        previous = run_git_command(['show', 'HEAD:'+filename], article.full_git_dir)
    except subprocess.CalledProcessError as e:
        if (e.output.endswith("does not exist in 'HEAD'\n") or
            e.output.endswith("exists on disk, but not in 'HEAD'.\n")):
            already_exists = False
        else:
            raise
    else:
        already_exists = True


    open(filename, 'w').write(data)

    if already_exists:
        if previous == data:
            logger.debug('Article matches current version in repo')
            return None, None, None, None

        #Now check how many times this same version has appeared before
        my_hash = run_git_command(['hash-object', filename],
                                  article.full_git_dir).strip()

        commits = [v.v for v in article.versions()]
        if len(commits) > 2:
            logger.debug('Checking for duplicates among %s commits',
                          len(commits))
            def get_hash(version):
                """Return the SHA1 hash of filename in a given version"""
                output = run_git_command(['ls-tree', '-r', version, filename],
                                         article.full_git_dir)
                return output.split()[2]
            hashes = map(get_hash, commits)

            number_equal = sum(1 for h in hashes if h == my_hash)

            logger.debug('Got %s', number_equal)

            if number_equal >= 2: #Refuse to list a version more than twice
                run_git_command(['checkout', filename], article.full_git_dir)
                return None, None, None, None

        if is_boring(previous, data):
            boring = True
        else:
            diff = get_diff(previous, data)

    run_git_command(['add', filename], article.full_git_dir)
    if not already_exists:
        commit_message = 'Adding file %s' % filename
    else:
        commit_message = 'Change to %s' % filename


    #logger.debug('done %s', time.time()-start_time)
    return article.full_git_dir, commit_message, boring, diff

def commit_git_repo(full_git_dir, commit_message):
    os.chdir(full_git_dir)

    start_time = time.time()

    logger.debug('Running git commit... %s', start_time)
    run_git_command(['commit', '-a', '-m', commit_message],
                    full_git_dir)
    logger.debug('git revlist... %s', time.time()-start_time)

def get_git_version(article):
    os.chdir(article.full_git_dir)
    # Now figure out what the commit ID was.
    # I would like this to be "git rev-list HEAD -n1 filename"
    # unfortunately, this command is slow: it doesn't abort after the
    # first line is output.  Without filename, it does abort; therefore
    # we do this and hope no intervening commit occurs.
    # (looks like the slowness is fixed in git HEAD)
    v = run_git_command(['rev-list', 'HEAD', '-n1', article.filename()],
                        article.full_git_dir).strip()

    return v


def load_article(url):
    try:
        parser = parsers.get_parser(url)
    except KeyError:
        logger.info('Unable to parse domain, skipping %s', url)
        return
    try:
        parsed_article = parser(url)
    except (AttributeError, urllib2.HTTPError, httplib.HTTPException), e:
        if isinstance(e, urllib2.HTTPError) and e.msg == 'Gone':
            return
        logger.error('Exception when parsing %s', url)
        logger.error(traceback.format_exc())
        logger.error('Continuing')
        return
    if not parsed_article.real_article:
        return
    return parsed_article

#Update url in git
#Return whether it changed
def update_article(article, parsed_article):
    article.last_check = datetime.now()
    if parsed_article is None:
        return
    to_store = unicode(parsed_article).encode('utf8')
    logger.debug('Article parsed; trying to store')
    git_dir, commit_message, boring, diff = add_to_git_repo(to_store,
                                           article.filename(),
                                           article)
    if git_dir:
        return git_dir, commit_message, parsed_article, boring, diff

def finalize_article_update(article, parsed_article, boring, diff):
    v = get_git_version(article)
    logger.info('Modifying! new blob: %s', v)
    t = datetime.now()
    v_row = models.Version(v=v,
                           boring=boring,
                           title=parsed_article.title,
                           byline=parsed_article.byline,
                           date=t,
                           article=article,
                           )
    v_row.diff_info = get_diff_info(diff)
    v_row.diff_details_json = json.dumps(diff,ensure_ascii=False)
    if diff:
        try:
            v_row.update_severity(save=False)
        except:
            print 'update_severity exception', diff
    if not boring:
        article.last_update = t
    v_row.save()
    article.save()

def update_articles(todays_git_dir):
    logger.info('Starting scraper; looking for new URLs')
    all_urls = get_all_article_urls()
    logger.info('Got all %s urls; storing to database' % len(all_urls))
    for i, url in enumerate(all_urls):
        logger.debug('Woo: %d/%d is %s' % (i+1, len(all_urls), url))
        if len(url) > 255:  #Icky hack, but otherwise they're truncated in DB.
            continue
        if not models.Article.objects.filter(url=url).count():
            logger.debug('Adding!')
            models.Article(url=url, git_dir=todays_git_dir).save()
    logger.info('Done storing to database')

def get_update_delay(minutes_since_update):
    days_since_update = minutes_since_update // (24 * 60)
    if minutes_since_update < 60*3:
        return 15
    elif days_since_update < 1:
        return 60
    elif days_since_update < 7:
        return 360
    elif days_since_update < 30:
        return 60*24*3
    elif days_since_update < 360:
        return 60*24*30
    else:
        return 60*24*365*1e5  #ignore old articles

def update_versions(todays_repo, do_all=False):
    logger.info('Looking for articles to check')
    articles = list(models.Article.objects.exclude(git_dir='old'))
    total_articles = len(articles)

    update_priority = lambda x: x.minutes_since_check() * 1. / get_update_delay(x.minutes_since_update())
    articles = sorted([a for a in articles if update_priority(a) > 1 or do_all],
                      key=update_priority, reverse=True)

    logger.info('Checking %s of %s articles', len(articles), total_articles)

    # Do git gc at the beginning, so if we're falling behind and killed
    # it still happens and I don't run out of quota. =)
    logger.info('Starting with gc:')
    try:
        run_git_command(['gc', '--auto'], models.GIT_DIR + todays_repo)
    except subprocess.CalledProcessError as e:
        print >> sys.stderr, 'Error on initial gc!'
        print >> sys.stderr, 'Output was """'
        print >> sys.stderr, e.output
        print >> sys.stderr, '"""'
        raise

    logger.info('Done!')

    articles_to_update = []

    for i, article in enumerate(articles):
        logger.debug('Woo: %s %s %s (%s/%s)',
                     article.minutes_since_update(),
                     article.minutes_since_check(),
                     update_priority(article), i+1, len(articles))
        delay = get_update_delay(article.minutes_since_update())
        if article.minutes_since_check() < delay and not do_all:
            continue
        articles_to_update.append(article)

    for i,article_batch in enumerate(batch(articles_to_update,300)):
        logger.debug('Batch %d of 300 of %d', i, len(articles_to_update))

        results = []
        update_results = []
        git_dirs_to_commit = collections.defaultdict(lambda: '')

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            future_to_article = {
                    executor.submit(load_article, article.url): article
                    for article in article_batch}

            try:
                for future in concurrent.futures.as_completed(future_to_article.keys(),
                        timeout=60*5 # 5 minute timeout per batch
                        ):
                    article = future_to_article[future]
                    try:
                        parsed_article = future.result()
                        results.append((article, parsed_article,))
                    except Exception, e:
                        logger.error('ThreadPool Exception when loading %s', article.url)
                        logger.error(traceback.format_exc())
                    if len(results)%100==0:
                        logger.info('Batch %d has %d results',
                                i, len(results))
            except concurrent.futures.TimeoutError, e:
                logger.error('TimeoutError in batch %d; results length %d, batch length %d, continuing', i, len(results), len(article_batch))



        for article,parsed_article in results:
            try:
                r = update_article(article, parsed_article)
                if r:
                    git_dir, commit_message, parsed_article, boring, diff = r
                    git_dirs_to_commit[git_dir] += '\n'+commit_message
            except Exception, e:
                if isinstance(e, subprocess.CalledProcessError):
                    logger.error('CalledProcessError when updating %s', article.url)
                    logger.error(repr(e.output))
                else:
                    logger.error('Unknown exception when updating %s', article.url)

                logger.error(traceback.format_exc())
                update_results.append(None)
            else:
                update_results.append(r)

        for gd,cm in git_dirs_to_commit.iteritems():
            commit_git_repo(gd,cm)

        for r2,r in itertools.izip(results,update_results):
            article, parsed_article = r2
            try:
                if r:
                    git_dir, commit_message, parsed_article, boring, diff = r
                    #commit_git_repo(article.full_git_dir, article.filename(), commit_message)
                    finalize_article_update(article, parsed_article,
                            boring, diff)
                article.save()
            except Exception, e:
                if isinstance(e, subprocess.CalledProcessError):
                    logger.error('CalledProcessError when updating %s', article.url)
                    logger.error(repr(e.output))
                else:
                    logger.error('Unknown exception when updating %s', article.url)

                logger.error(traceback.format_exc())
    #logger.info('Ending with gc:')
    #run_git_command(['gc'])
    logger.info('Done!')

#Remove index.lock if 5 minutes old
def cleanup_git_repo(git_dir):
    for name in ['.git/index.lock', '.git/refs/heads/master.lock', '.git/gc.pid.lock']:
        fname = os.path.join(git_dir, name)
        try:
            stat = os.stat(fname)
        except OSError:
            return
        age = time.time() - stat.st_ctime
        if age > 60*5:
            os.remove(fname)


if __name__ == '__main__':
    print >> sys.stderr, "Try `python website/manage.py scraper`."
