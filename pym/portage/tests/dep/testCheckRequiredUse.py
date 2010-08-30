# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from portage.tests import TestCase
from portage.dep import check_required_use
from portage.exception import InvalidDependString

class TestCheckRequiredUse(TestCase):

	def testCheckRequiredUse(self):
		test_cases = (
			( "|| ( a b )", [], ["a", "b"], False),
			( "|| ( a b )", ["a"], ["a", "b"], True),
			( "|| ( a b )", ["b"], ["a", "b"], True),
			( "|| ( a b )", ["a", "b"], ["a", "b"], True),

			( "^^ ( a b )", [], ["a", "b"], False),
			( "^^ ( a b )", ["a"], ["a", "b"], True),
			( "^^ ( a b )", ["b"], ["a", "b"], True),
			( "^^ ( a b )", ["a", "b"], ["a", "b"], False),

			( "^^ ( || ( a b ) c )", [], ["a", "b", "c"], False),
			( "^^ ( || ( a b ) c )", ["a"], ["a", "b", "c"], True),

			( "^^ ( || ( ( a b ) ) ( c ) )", [], ["a", "b", "c"], False),
			( "( ^^ ( ( || ( ( a ) ( b ) ) ) ( ( c ) ) ) )", ["a"], ["a", "b", "c"], True),

			( "a || ( b c )", ["a"], ["a", "b", "c"], False),
			( "|| ( b c ) a", ["a"], ["a", "b", "c"], False),

			( "|| ( a b c )", ["a"], ["a", "b", "c"], True),
			( "|| ( a b c )", ["b"], ["a", "b", "c"], True),
			( "|| ( a b c )", ["c"], ["a", "b", "c"], True),

			( "^^ ( a b c )", ["a"], ["a", "b", "c"], True),
			( "^^ ( a b c )", ["b"], ["a", "b", "c"], True),
			( "^^ ( a b c )", ["c"], ["a", "b", "c"], True),
			( "^^ ( a b c )", ["a", "b"], ["a", "b", "c"], False),
			( "^^ ( a b c )", ["b", "c"], ["a", "b", "c"], False),
			( "^^ ( a b c )", ["a", "c"], ["a", "b", "c"], False),
			( "^^ ( a b c )", ["a", "b", "c"], ["a", "b", "c"], False),

			( "a? ( ^^ ( b c ) )", [], ["a", "b", "c"], True),
			( "a? ( ^^ ( b c ) )", ["a"], ["a", "b", "c"], False),
			( "a? ( ^^ ( b c ) )", ["b"], ["a", "b", "c"], True),
			( "a? ( ^^ ( b c ) )", ["c"], ["a", "b", "c"], True),
			( "a? ( ^^ ( b c ) )", ["a", "b"], ["a", "b", "c"], True),
			( "a? ( ^^ ( b c ) )", ["a", "b", "c"], ["a", "b", "c"], False),

			( "^^ ( a? ( !b ) !c? ( d ) )", [], ["a", "b", "c", "d"], False),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["a"], ["a", "b", "c", "d"], True),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["c"], ["a", "b", "c", "d"], True),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["a", "c"], ["a", "b", "c", "d"], True),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["a", "b", "c"], ["a", "b", "c", "d"], False),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["a", "b", "d"], ["a", "b", "c", "d"], True),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["a", "b", "d"], ["a", "b", "c", "d"], True),
			( "^^ ( a? ( !b ) !c? ( d ) )", ["a", "d"], ["a", "b", "c", "d"], False),

			( "|| ( ^^ ( a b ) ^^ ( b c ) )", [], ["a", "b", "c"], False),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["a"], ["a", "b", "c"], True),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["b"], ["a", "b", "c"], True),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["c"], ["a", "b", "c"], True),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["a", "b"], ["a", "b", "c"], True),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["a", "c"], ["a", "b", "c"], True),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["b", "c"], ["a", "b", "c"], True),
			( "|| ( ^^ ( a b ) ^^ ( b c ) )", ["a", "b", "c"], ["a", "b", "c"], False),

			( "^^ ( || ( a b ) ^^ ( b c ) )", [], ["a", "b", "c"], False),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["a"], ["a", "b", "c"], True),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["b"], ["a", "b", "c"], False),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["c"], ["a", "b", "c"], True),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["a", "b"], ["a", "b", "c"], False),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["a", "c"], ["a", "b", "c"], False),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["b", "c"], ["a", "b", "c"], True),
			( "^^ ( || ( a b ) ^^ ( b c ) )", ["a", "b", "c"], ["a", "b", "c"], True),

			( "|| ( ( a b ) c )", ["a", "b", "c"], ["a", "b", "c"], True),
			( "|| ( ( a b ) c )", ["b", "c"], ["a", "b", "c"], True),
			( "|| ( ( a b ) c )", ["a", "c"], ["a", "b", "c"], True),
			( "|| ( ( a b ) c )", ["a", "b"], ["a", "b", "c"], True),
			( "|| ( ( a b ) c )", ["a"], ["a", "b", "c"], False),
			( "|| ( ( a b ) c )", ["b"], ["a", "b", "c"], False),
			( "|| ( ( a b ) c )", ["c"], ["a", "b", "c"], True),
			( "|| ( ( a b ) c )", [], ["a", "b", "c"], False),

			( "^^ ( ( a b ) c )", ["a", "b", "c"], ["a", "b", "c"], False),
			( "^^ ( ( a b ) c )", ["b", "c"], ["a", "b", "c"], True),
			( "^^ ( ( a b ) c )", ["a", "c"], ["a", "b", "c"], True),
			( "^^ ( ( a b ) c )", ["a", "b"], ["a", "b", "c"], True),
			( "^^ ( ( a b ) c )", ["a"], ["a", "b", "c"], False),
			( "^^ ( ( a b ) c )", ["b"], ["a", "b", "c"], False),
			( "^^ ( ( a b ) c )", ["c"], ["a", "b", "c"], True),
			( "^^ ( ( a b ) c )", [], ["a", "b", "c"], False),
		)

		test_cases_xfail = (
			( "^^ ( || ( a b ) ^^ ( b c ) )", [], ["a", "b"]),
			( "^^ ( || ( a b ) ^^ ( b c )", [], ["a", "b", "c"]),
			( "^^( || ( a b ) ^^ ( b c ) )", [], ["a", "b", "c"]),
			( "^^ || ( a b ) ^^ ( b c )", [], ["a", "b", "c"]),
			( "^^ ( ( || ) ( a b ) ^^ ( b c ) )", [], ["a", "b", "c"]),
			( "^^ ( || ( a b ) ) ^^ ( b c ) )", [], ["a", "b", "c"]),
		)

		for required_use, use, iuse, expected in test_cases:
			self.assertEqual(check_required_use(required_use, use, iuse.__contains__), \
				expected, required_use + ", USE = " + " ".join(use))

		for required_use, use, iuse in test_cases_xfail:
			self.assertRaisesMsg(required_use + ", USE = " + " ".join(use), \
				InvalidDependString, check_required_use, required_use, use, iuse.__contains__)
