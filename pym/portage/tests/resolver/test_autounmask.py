# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from portage.tests import TestCase
from portage.tests.resolver.ResolverPlayground import ResolverPlayground, ResolverPlaygroundTestCase

class AutounmaskTestCase(TestCase):

	def testAutounmask(self):
		ebuilds = {
			#ebuilds to test use changes
			"dev-libs/A-1": { "SLOT": 1, "DEPEND": "dev-libs/B[foo]", "EAPI": 2}, 
			"dev-libs/A-2": { "SLOT": 2, "DEPEND": "dev-libs/B[bar]", "EAPI": 2}, 
			"dev-libs/B-1": { "DEPEND": "foo? ( dev-libs/C ) bar? ( dev-libs/D )", "IUSE": "foo bar"}, 
			"dev-libs/C-1": {},
			"dev-libs/D-1": {},

			#ebuilds to test keyword changes
			"app-misc/Z-1": { "KEYWORDS": "~x86", "DEPEND": "app-misc/Y" },
			"app-misc/Y-1": { "KEYWORDS": "~x86" },
			"app-misc/W-1": {},
			"app-misc/W-2": { "KEYWORDS": "~x86" },
			"app-misc/V-1": { "KEYWORDS": "~x86", "DEPEND": ">=app-misc/W-2"},

			#ebuilds for mixed test for || dep handling
			"sci-libs/K-1": { "DEPEND": " || ( sci-libs/L[bar] || ( sci-libs/M sci-libs/P ) )", "EAPI": 2},
			"sci-libs/K-2": { "DEPEND": " || ( sci-libs/L[bar] || ( sci-libs/P sci-libs/M ) )", "EAPI": 2},
			"sci-libs/K-3": { "DEPEND": " || ( sci-libs/M || ( sci-libs/L[bar] sci-libs/P ) )", "EAPI": 2},
			"sci-libs/K-4": { "DEPEND": " || ( sci-libs/M || ( sci-libs/P sci-libs/L[bar] ) )", "EAPI": 2},
			"sci-libs/K-5": { "DEPEND": " || ( sci-libs/P || ( sci-libs/L[bar] sci-libs/M ) )", "EAPI": 2},
			"sci-libs/K-6": { "DEPEND": " || ( sci-libs/P || ( sci-libs/M sci-libs/L[bar] ) )", "EAPI": 2},
			"sci-libs/K-7": { "DEPEND": " || ( sci-libs/M sci-libs/L[bar] )", "EAPI": 2},
			"sci-libs/K-8": { "DEPEND": " || ( sci-libs/L[bar] sci-libs/M )", "EAPI": 2},

			"sci-libs/L-1": { "IUSE": "bar" },
			"sci-libs/M-1": { "KEYWORDS": "~x86" },
			"sci-libs/P-1": { },

			#ebuilds to test these nice "required by cat/pkg[foo]" messages
			"dev-util/Q-1": { "DEPEND": "foo? ( dev-util/R[bar] )", "IUSE": "+foo", "EAPI": 2 },
			"dev-util/Q-2": { "RDEPEND": "!foo? ( dev-util/R[bar] )", "IUSE": "foo", "EAPI": 2 },
			"dev-util/R-1": { "IUSE": "bar" },

			#ebuilds to test interaction with REQUIRED_USE
			#~ "app-portage/A-1": { "DEPEND": "app-portage/B[foo]", "EAPI": 2 }, 
			#~ "app-portage/A-2": { "DEPEND": "app-portage/B[foo=]", "IUSE": "+foo", "REQUIRED_USE": "foo", "EAPI": 4 }, 
#~ 
			#~ "app-portage/B-1": { "IUSE": "foo +bar", "REQUIRED_USE": "^^ ( foo bar )", "EAPI": 4 }, 
			}

		test_cases = (
				#Test USE changes.
				#The simple case.

				ResolverPlaygroundTestCase(
					["dev-libs/A:1"],
					options = {"--autounmask": "n"},
					success = False),
				ResolverPlaygroundTestCase(
					["dev-libs/A:1"],
					options = {"--autounmask": True},
					success = False,
					mergelist = ["dev-libs/C-1", "dev-libs/B-1", "dev-libs/A-1"],
					use_changes = { "dev-libs/B-1": {"foo": True} } ),

				#Make sure we restart if needed.
				ResolverPlaygroundTestCase(
					["dev-libs/A:1", "dev-libs/B"],
					options = {"--autounmask": True},
					all_permutations = True,
					success = False,
					mergelist = ["dev-libs/C-1", "dev-libs/B-1", "dev-libs/A-1"],
					use_changes = { "dev-libs/B-1": {"foo": True} } ),
				ResolverPlaygroundTestCase(
					["dev-libs/A:1", "dev-libs/A:2", "dev-libs/B"],
					options = {"--autounmask": True},
					all_permutations = True,
					success = False,
					mergelist = ["dev-libs/D-1", "dev-libs/C-1", "dev-libs/B-1", "dev-libs/A-1", "dev-libs/A-2"],
					ignore_mergelist_order = True,
					use_changes = { "dev-libs/B-1": {"foo": True, "bar": True} } ),

				#Test keywording.
				#The simple case.

				ResolverPlaygroundTestCase(
					["app-misc/Z"],
					options = {"--autounmask": "n"},
					success = False),
				ResolverPlaygroundTestCase(
					["app-misc/Z"],
					options = {"--autounmask": True},
					success = False,
					mergelist = ["app-misc/Y-1", "app-misc/Z-1"],
					unstable_keywords = ["app-misc/Y-1", "app-misc/Z-1"]),

				#Make sure that the backtracking for slot conflicts handles our mess.

				ResolverPlaygroundTestCase(
					["=app-misc/V-1", "app-misc/W"],
					options = {"--autounmask": True},
					all_permutations = True,
					success = False,
					mergelist = ["app-misc/W-2", "app-misc/V-1"],
					unstable_keywords = ["app-misc/W-2", "app-misc/V-1"]),

				#Mixed testing
				#Make sure we don't change use for something in a || dep if there is another choice
				#that needs no change.
				
				ResolverPlaygroundTestCase(
					["=sci-libs/K-1"],
					options = {"--autounmask": True},
					success = True,
					mergelist = ["sci-libs/P-1", "sci-libs/K-1"]),
				ResolverPlaygroundTestCase(
					["=sci-libs/K-2"],
					options = {"--autounmask": True},
					success = True,
					mergelist = ["sci-libs/P-1", "sci-libs/K-2"]),
				ResolverPlaygroundTestCase(
					["=sci-libs/K-3"],
					options = {"--autounmask": True},
					success = True,
					mergelist = ["sci-libs/P-1", "sci-libs/K-3"]),
				ResolverPlaygroundTestCase(
					["=sci-libs/K-4"],
					options = {"--autounmask": True},
					success = True,
					mergelist = ["sci-libs/P-1", "sci-libs/K-4"]),
				ResolverPlaygroundTestCase(
					["=sci-libs/K-5"],
					options = {"--autounmask": True},
					success = True,
					mergelist = ["sci-libs/P-1", "sci-libs/K-5"]),
				ResolverPlaygroundTestCase(
					["=sci-libs/K-6"],
					options = {"--autounmask": True},
					success = True,
					mergelist = ["sci-libs/P-1", "sci-libs/K-6"]),

				#Make sure we prefer use changes over keyword changes.
				ResolverPlaygroundTestCase(
					["=sci-libs/K-7"],
					options = {"--autounmask": True},
					success = False,
					mergelist = ["sci-libs/L-1", "sci-libs/K-7"],
					use_changes = { "sci-libs/L-1": { "bar": True } }),
				ResolverPlaygroundTestCase(
					["=sci-libs/K-8"],
					options = {"--autounmask": True},
					success = False,
					mergelist = ["sci-libs/L-1", "sci-libs/K-8"],
					use_changes = { "sci-libs/L-1": { "bar": True } }),

				#Test these nice "required by cat/pkg[foo]" messages.
				ResolverPlaygroundTestCase(
					["=dev-util/Q-1"],
					options = {"--autounmask": True},
					success = False,
					mergelist = ["dev-util/R-1", "dev-util/Q-1"],
					use_changes = { "dev-util/R-1": { "bar": True } }),
				ResolverPlaygroundTestCase(
					["=dev-util/Q-2"],
					options = {"--autounmask": True},
					success = False,
					mergelist = ["dev-util/R-1", "dev-util/Q-2"],
					use_changes = { "dev-util/R-1": { "bar": True } }),

				#Test interaction with REQUIRED_USE.
				#~ ResolverPlaygroundTestCase(
					#~ ["=app-portage/A-1"],
					#~ options = { "--autounmask": True },
					#~ use_changes = None,
					#~ success = False),
				#~ ResolverPlaygroundTestCase(
					#~ ["=app-portage/A-2"],
					#~ options = { "--autounmask": True },
					#~ use_changes = None,
					#~ success = False),
			)

		playground = ResolverPlayground(ebuilds=ebuilds)
		try:
			for test_case in test_cases:
				playground.run_TestCase(test_case)
				self.assertEqual(test_case.test_success, True, test_case.fail_msg)
		finally:
			playground.cleanup()
