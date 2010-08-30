# Copyright 2006, 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import sys
from portage.tests import TestCase
from portage.dep import Atom, match_from_list
from portage.versions import catpkgsplit

if sys.hexversion >= 0x3000000:
	basestring = str

class Package(object):
	"""
	Provides a minimal subset of attributes of _emerge.Package.Package
	"""
	def __init__(self, atom):
		atom = Atom(atom)
		self.cp = atom.cp
		self.cpv = atom.cpv
		self.cpv_split = catpkgsplit(self.cpv)
		self.slot = atom.slot
		if atom.use:
			self.use = self._use_class(atom.use.enabled)
			self.iuse = self._iuse_class(atom.use.required)
		else:
			self.use = self._use_class([])
			self.iuse = self._iuse_class([])

	class _use_class(object):
		def __init__(self, use):
			self.enabled = frozenset(use)

	class _iuse_class(object):
		def __init__(self, iuse):
			self.all = frozenset(iuse)

		def is_valid_flag(self, flags):
			if isinstance(flags, basestring):
				flags = [flags]
			missing_iuse = []
			for flag in flags:
				if not flag in self.all:
					return False
			return True

class Test_match_from_list(TestCase):

	def testMatch_from_list(self):
		tests = (
			("=sys-apps/portage-45*", [], [] ),
			("=sys-apps/portage-45*", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			("!=sys-apps/portage-45*", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			("!!=sys-apps/portage-45*", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			("=sys-apps/portage-045", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			("=sys-apps/portage-045", ["sys-apps/portage-046"], [] ),
			("~sys-apps/portage-045", ["sys-apps/portage-045-r1"], ["sys-apps/portage-045-r1"] ),
			("~sys-apps/portage-045", ["sys-apps/portage-046-r1"], [] ),
			("<=sys-apps/portage-045", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			("<=sys-apps/portage-045", ["sys-apps/portage-046"], [] ),
			("<sys-apps/portage-046", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			("<sys-apps/portage-046", ["sys-apps/portage-046"], [] ),
			(">=sys-apps/portage-045", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			(">=sys-apps/portage-047", ["sys-apps/portage-046-r1"], [] ),
			(">sys-apps/portage-044", ["sys-apps/portage-045"], ["sys-apps/portage-045"] ),
			(">sys-apps/portage-047", ["sys-apps/portage-046-r1"], [] ),
			("sys-apps/portage:0", [Package("=sys-apps/portage-045:0")], ["sys-apps/portage-045"] ),
			("sys-apps/portage:0", [Package("=sys-apps/portage-045:1")], [] ),
			("=sys-fs/udev-1*", ["sys-fs/udev-123"], ["sys-fs/udev-123"]),
			("=sys-fs/udev-4*", ["sys-fs/udev-456"], ["sys-fs/udev-456"] ),
			("*/*", ["sys-fs/udev-456"], ["sys-fs/udev-456"] ),
			("sys-fs/*", ["sys-fs/udev-456"], ["sys-fs/udev-456"] ),
			("*/udev", ["sys-fs/udev-456"], ["sys-fs/udev-456"] ),
			("=sys-apps/portage-2*", ["sys-apps/portage-2.1"], ["sys-apps/portage-2.1"] ),
			("=sys-apps/portage-2.1*", ["sys-apps/portage-2.1.2"], ["sys-apps/portage-2.1.2"] ),
			("dev-libs/*", ["sys-apps/portage-2.1.2"], [] ),
			("*/tar", ["sys-apps/portage-2.1.2"], [] ),
			("*/*", ["dev-libs/A-1", "dev-libs/B-1"], ["dev-libs/A-1", "dev-libs/B-1"] ),
			("dev-libs/*", ["dev-libs/A-1", "sci-libs/B-1"], ["dev-libs/A-1"] ),
			
			("dev-libs/A[foo]", [Package("=dev-libs/A-1[foo]"), Package("=dev-libs/A-2[-foo]")], ["dev-libs/A-1"] ),
			("dev-libs/A[-foo]", [Package("=dev-libs/A-1[foo]"), Package("=dev-libs/A-2[-foo]")], ["dev-libs/A-2"] ),
			("dev-libs/A[-foo]", [Package("=dev-libs/A-1[foo]"), Package("=dev-libs/A-2")], [] ),
			("dev-libs/A[foo,bar]", [Package("=dev-libs/A-1[foo]"), Package("=dev-libs/A-2[-foo]")], [] ),
			("dev-libs/A[foo,bar]", [Package("=dev-libs/A-1[foo]"), Package("=dev-libs/A-2[-foo,bar]")], [] ),
			("dev-libs/A[foo,bar]", [Package("=dev-libs/A-1[foo]"), Package("=dev-libs/A-2[foo,bar]")], ["dev-libs/A-2"] ),
			("dev-libs/A[foo,bar(+)]", [Package("=dev-libs/A-1[-foo]"), Package("=dev-libs/A-2[foo]")], ["dev-libs/A-2"] ),
			("dev-libs/A[foo,bar(-)]", [Package("=dev-libs/A-1[-foo]"), Package("=dev-libs/A-2[foo]")], [] ),
			("dev-libs/A[foo,-bar(-)]", [Package("=dev-libs/A-1[-foo,bar]"), Package("=dev-libs/A-2[foo]")], ["dev-libs/A-2"] ),
		)

		for atom, cpv_list, expected_result in tests:
			result = []
			for pkg in match_from_list( atom, cpv_list ):
				if isinstance(pkg, Package):
					result.append(pkg.cpv)
				else:
					result.append(pkg)
			self.assertEqual( result, expected_result )
