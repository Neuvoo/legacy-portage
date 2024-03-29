# archive_conf.py -- functionality common to archive-conf and dispatch-conf
# Copyright 2003-2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2


# Library by Wayne Davison <gentoo@blorf.net>, derived from code
# written by Jeremy Wohl (http://igmus.org)

from __future__ import print_function

import os, sys, shutil
try:
    from subprocess import getstatusoutput as subprocess_getstatusoutput
except ImportError:
    from commands import getstatusoutput as subprocess_getstatusoutput

import portage
from portage.localization import _

RCS_BRANCH = '1.1.1'
RCS_LOCK = 'rcs -ko -M -l'
RCS_PUT = 'ci -t-"Archived config file." -m"dispatch-conf update."'
RCS_GET = 'co'
RCS_MERGE = "rcsmerge -p -r" + RCS_BRANCH + " '%s' > '%s'"

DIFF3_MERGE = "diff3 -mE '%s' '%s' '%s' > '%s'"

def diffstatusoutput_len(cmd):
    """
    Execute the string cmd in a shell with getstatusoutput() and return a
    2-tuple (status, output_length). If getstatusoutput() raises
    UnicodeDecodeError (known to happen with python3.1), return a
    2-tuple (1, 1). This provides a simple way to check for non-zero
    output length of diff commands, while providing simple handling of
    UnicodeDecodeError when necessary.
    """
    try:
        status, output = subprocess_getstatusoutput(cmd)
        return (status, len(output))
    except UnicodeDecodeError:
        return (1, 1)

def read_config(mandatory_opts):
    loader = portage.env.loaders.KeyValuePairFileLoader(
        '/etc/dispatch-conf.conf', None)
    opts, errors = loader.load()
    if not opts:
        print(_('dispatch-conf: Error reading /etc/dispatch-conf.conf; fatal'), file=sys.stderr)
        sys.exit(1)

	# Handle quote removal here, since KeyValuePairFileLoader doesn't do that.
    quotes = "\"'"
    for k, v in opts.items():
        if v[:1] in quotes and v[:1] == v[-1:]:
            opts[k] = v[1:-1]

    for key in mandatory_opts:
        if key not in opts:
            if key == "merge":
                opts["merge"] = "sdiff --suppress-common-lines --output='%s' '%s' '%s'"
            else:
                print(_('dispatch-conf: Missing option "%s" in /etc/dispatch-conf.conf; fatal') % (key,), file=sys.stderr)

    if not os.path.exists(opts['archive-dir']):
        os.mkdir(opts['archive-dir'])
    elif not os.path.isdir(opts['archive-dir']):
        print(_('dispatch-conf: Config archive dir [%s] must exist; fatal') % (opts['archive-dir'],), file=sys.stderr)
        sys.exit(1)

    return opts


def rcs_archive(archive, curconf, newconf, mrgconf):
    """Archive existing config in rcs (on trunk). Then, if mrgconf is
    specified and an old branch version exists, merge the user's changes
    and the distributed changes and put the result into mrgconf.  Lastly,
    if newconf was specified, leave it in the archive dir with a .dist.new
    suffix along with the last 1.1.1 branch version with a .dist suffix."""

    try:
        os.makedirs(os.path.dirname(archive))
    except OSError:
        pass

    try:
        shutil.copy2(curconf, archive)
    except(IOError, os.error) as why:
        print(_('dispatch-conf: Error copying %(curconf)s to %(archive)s: %(reason)s; fatal') % \
              {"curconf": curconf, "archive": archive, "reason": str(why)}, file=sys.stderr)
    if os.path.exists(archive + ',v'):
        os.system(RCS_LOCK + ' ' + archive)
    os.system(RCS_PUT + ' ' + archive)

    ret = 0
    if newconf != '':
        os.system(RCS_GET + ' -r' + RCS_BRANCH + ' ' + archive)
        has_branch = os.path.exists(archive)
        if has_branch:
            os.rename(archive, archive + '.dist')

        try:
            shutil.copy2(newconf, archive)
        except(IOError, os.error) as why:
            print(_('dispatch-conf: Error copying %(newconf)s to %(archive)s: %(reason)s; fatal') % \
                  {"newconf": newconf, "archive": archive, "reason": str(why)}, file=sys.stderr)

        if has_branch:
            if mrgconf != '':
                # This puts the results of the merge into mrgconf.
                ret = os.system(RCS_MERGE % (archive, mrgconf))
                mystat = os.lstat(newconf)
                os.chmod(mrgconf, mystat.st_mode)
                os.chown(mrgconf, mystat.st_uid, mystat.st_gid)
        os.rename(archive, archive + '.dist.new')
    return ret


def file_archive(archive, curconf, newconf, mrgconf):
    """Archive existing config to the archive-dir, bumping old versions
    out of the way into .# versions (log-rotate style). Then, if mrgconf
    was specified and there is a .dist version, merge the user's changes
    and the distributed changes and put the result into mrgconf.  Lastly,
    if newconf was specified, archive it as a .dist.new version (which
    gets moved to the .dist version at the end of the processing)."""

    try:
        os.makedirs(os.path.dirname(archive))
    except OSError:
        pass

    # Archive the current config file if it isn't already saved
    if os.path.exists(archive) \
     and diffstatusoutput_len("diff -aq '%s' '%s'" % (curconf,archive))[1] != 0:
        suf = 1
        while suf < 9 and os.path.exists(archive + '.' + str(suf)):
            suf += 1

        while suf > 1:
            os.rename(archive + '.' + str(suf-1), archive + '.' + str(suf))
            suf -= 1

        os.rename(archive, archive + '.1')

    try:
        shutil.copy2(curconf, archive)
    except(IOError, os.error) as why:
        print(_('dispatch-conf: Error copying %(curconf)s to %(archive)s: %(reason)s; fatal') % \
              {"curconf": curconf, "archive": archive, "reason": str(why)}, file=sys.stderr)

    if newconf != '':
        # Save off new config file in the archive dir with .dist.new suffix
        try:
            shutil.copy2(newconf, archive + '.dist.new')
        except(IOError, os.error) as why:
            print(_('dispatch-conf: Error copying %(newconf)s to %(archive)s: %(reason)s; fatal') % \
                  {"newconf": newconf, "archive": archive + '.dist.new', "reason": str(why)}, file=sys.stderr)

        ret = 0
        if mrgconf != '' and os.path.exists(archive + '.dist'):
            # This puts the results of the merge into mrgconf.
            ret = os.system(DIFF3_MERGE % (curconf, archive + '.dist', newconf, mrgconf))
            mystat = os.lstat(newconf)
            os.chmod(mrgconf, mystat.st_mode)
            os.chown(mrgconf, mystat.st_uid, mystat.st_gid)

        return ret


def rcs_archive_post_process(archive):
    """Check in the archive file with the .dist.new suffix on the branch
    and remove the one with the .dist suffix."""
    os.rename(archive + '.dist.new', archive)
    if os.path.exists(archive + '.dist'):
        # Commit the last-distributed version onto the branch.
        os.system(RCS_LOCK + RCS_BRANCH + ' ' + archive)
        os.system(RCS_PUT + ' -r' + RCS_BRANCH + ' ' + archive)
        os.unlink(archive + '.dist')
    else:
        # Forcefully commit the last-distributed version onto the branch.
        os.system(RCS_PUT + ' -f -r' + RCS_BRANCH + ' ' + archive)


def file_archive_post_process(archive):
    """Rename the archive file with the .dist.new suffix to a .dist suffix"""
    os.rename(archive + '.dist.new', archive + '.dist')
