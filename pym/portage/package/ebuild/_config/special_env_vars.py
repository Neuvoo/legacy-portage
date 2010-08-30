# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

__all__ = (
	'case_insensitive_vars', 'default_globals', 'env_blacklist', \
	'environ_filter', 'environ_whitelist', 'environ_whitelist_re',
)

import re

env_blacklist = frozenset((
	"A", "AA", "CATEGORY", "DEPEND", "DESCRIPTION", "EAPI",
	"EBUILD_PHASE", "ED", "EMERGE_FROM", "EPREFIX", "EROOT",
	"HOMEPAGE", "INHERITED", "IUSE",
	"KEYWORDS", "LICENSE", "PDEPEND", "PF", "PKGUSE",
	"PORTAGE_CONFIGROOT", "PORTAGE_IUSE",
	"PORTAGE_NONFATAL", "PORTAGE_REPO_NAME",
	"PORTAGE_USE", "PROPERTIES", "PROVIDE", "RDEPEND", "RESTRICT",
	"ROOT", "SLOT", "SRC_URI"
))

environ_whitelist = []

# Whitelisted variables are always allowed to enter the ebuild
# environment. Generally, this only includes special portage
# variables. Ebuilds can unset variables that are not whitelisted
# and rely on them remaining unset for future phases, without them
# leaking back in from various locations (bug #189417). It's very
# important to set our special BASH_ENV variable in the ebuild
# environment in order to prevent sandbox from sourcing /etc/profile
# in it's bashrc (causing major leakage).
environ_whitelist += [
	"ACCEPT_LICENSE", "BASH_ENV", "BUILD_PREFIX", "D",
	"DISTDIR", "DOC_SYMLINKS_DIR", "EAPI", "EBUILD",
	"EBUILD_FORCE_TEST",
	"EBUILD_PHASE", "ECLASSDIR", "ECLASS_DEPTH", "ED",
	"EMERGE_FROM", "EPREFIX", "EROOT",
	"FEATURES", "FILESDIR", "HOME", "NOCOLOR", "PATH",
	"PKGDIR",
	"PKGUSE", "PKG_LOGDIR", "PKG_TMPDIR",
	"PORTAGE_ACTUAL_DISTDIR", "PORTAGE_ARCHLIST",
	"PORTAGE_BASHRC", "PM_EBUILD_HOOK_DIR",
	"PORTAGE_BINPKG_FILE", "PORTAGE_BINPKG_TAR_OPTS",
	"PORTAGE_BINPKG_TMPFILE",
	"PORTAGE_BIN_PATH",
	"PORTAGE_BUILDDIR", "PORTAGE_COLORMAP",
	"PORTAGE_CONFIGROOT", "PORTAGE_DEBUG", "PORTAGE_DEPCACHEDIR",
	"PORTAGE_EBUILD_EXIT_FILE", "PORTAGE_FEATURES",
	"PORTAGE_GID", "PORTAGE_GRPNAME",
	"PORTAGE_INST_GID", "PORTAGE_INST_UID",
	"PORTAGE_IPC_DAEMON", "PORTAGE_IUSE",
	"PORTAGE_LOG_FILE", "PORTAGE_MASTER_PID",
	"PORTAGE_PYM_PATH", "PORTAGE_PYTHON", "PORTAGE_QUIET",
	"PORTAGE_REPO_NAME", "PORTAGE_RESTRICT", "PORTAGE_SIGPIPE_STATUS",
	"PORTAGE_TMPDIR", "PORTAGE_UPDATE_ENV", "PORTAGE_USERNAME",
	"PORTAGE_VERBOSE", "PORTAGE_WORKDIR_MODE",
	"PORTDIR", "PORTDIR_OVERLAY", "PREROOTPATH", "PROFILE_PATHS",
	"REPLACING_VERSIONS", "REPLACED_BY_VERSION",
	"ROOT", "ROOTPATH", "T", "TMP", "TMPDIR",
	"USE_EXPAND", "USE_ORDER", "WORKDIR",
	"XARGS",
]

# user config variables
environ_whitelist += [
	"DOC_SYMLINKS_DIR", "INSTALL_MASK", "PKG_INSTALL_MASK"
]

environ_whitelist += [
	"A", "AA", "CATEGORY", "P", "PF", "PN", "PR", "PV", "PVR"
]

# misc variables inherited from the calling environment
environ_whitelist += [
	"COLORTERM", "DISPLAY", "EDITOR", "LESS",
	"LESSOPEN", "LOGNAME", "LS_COLORS", "PAGER",
	"TERM", "TERMCAP", "USER",
]

# tempdir settings
environ_whitelist += [
	"TMPDIR", "TEMP", "TMP",
]

# localization settings
environ_whitelist += [
	"LANG", "LC_COLLATE", "LC_CTYPE", "LC_MESSAGES",
	"LC_MONETARY", "LC_NUMERIC", "LC_TIME", "LC_PAPER",
	"LC_ALL",
]

# other variables inherited from the calling environment
environ_whitelist += [
	"CVS_RSH", "ECHANGELOG_USER",
	"GPG_AGENT_INFO",
	"SSH_AGENT_PID", "SSH_AUTH_SOCK",
	"STY", "WINDOW", "XAUTHORITY",
]

environ_whitelist = frozenset(environ_whitelist)

environ_whitelist_re = re.compile(r'^(CCACHE_|DISTCC_).*')

# Filter selected variables in the config.environ() method so that
# they don't needlessly propagate down into the ebuild environment.
environ_filter = []

# Exclude anything that could be extremely long here (like SRC_URI)
# since that could cause execve() calls to fail with E2BIG errors. For
# example, see bug #262647.
environ_filter += [
	'DEPEND', 'RDEPEND', 'PDEPEND', 'SRC_URI',
]

# misc variables inherited from the calling environment
environ_filter += [
	"INFOPATH", "MANPATH", "USER",
]

# variables that break bash
environ_filter += [
	"HISTFILE", "POSIXLY_CORRECT",
]

# portage config variables and variables set directly by portage
environ_filter += [
	"ACCEPT_KEYWORDS", "ACCEPT_PROPERTIES", "AUTOCLEAN",
	"CLEAN_DELAY", "COLLISION_IGNORE", "CONFIG_PROTECT",
	"CONFIG_PROTECT_MASK", "EGENCACHE_DEFAULT_OPTS", "EMERGE_DEFAULT_OPTS",
	"EMERGE_LOG_DIR",
	"EMERGE_WARNING_DELAY", "FETCHCOMMAND", "FETCHCOMMAND_FTP",
	"FETCHCOMMAND_HTTP", "FETCHCOMMAND_SFTP",
	"GENTOO_MIRRORS", "NOCONFMEM", "O",
	"PORTAGE_BACKGROUND",
	"PORTAGE_BINHOST_CHUNKSIZE", "PORTAGE_CALLER",
	"PORTAGE_ELOG_CLASSES",
	"PORTAGE_ELOG_MAILFROM", "PORTAGE_ELOG_MAILSUBJECT",
	"PORTAGE_ELOG_MAILURI", "PORTAGE_ELOG_SYSTEM",
	"PORTAGE_FETCH_CHECKSUM_TRY_MIRRORS", "PORTAGE_FETCH_RESUME_MIN_SIZE",
	"PORTAGE_GPG_DIR",
	"PORTAGE_GPG_KEY", "PORTAGE_IONICE_COMMAND",
	"PORTAGE_PACKAGE_EMPTY_ABORT",
	"PORTAGE_REPO_DUPLICATE_WARN",
	"PORTAGE_RO_DISTDIRS",
	"PORTAGE_RSYNC_EXTRA_OPTS", "PORTAGE_RSYNC_OPTS",
	"PORTAGE_RSYNC_RETRIES", "PORTAGE_SYNC_STALE",
	"PORTAGE_USE", "PORT_LOGDIR",
	"QUICKPKG_DEFAULT_OPTS",
	"RESUMECOMMAND", "RESUMECOMMAND_HTTP", "RESUMECOMMAND_HTTP",
	"RESUMECOMMAND_SFTP", "SYNC", "USE_EXPAND_HIDDEN", "USE_ORDER",
]

environ_filter = frozenset(environ_filter)

default_globals = (
	('ACCEPT_LICENSE',           '* -@EULA'),
	('ACCEPT_PROPERTIES',        '*'),
)

# To enhance usability, make some vars case insensitive
# by forcing them to lower case.
case_insensitive_vars = ('AUTOCLEAN', 'NOCOLOR',)
