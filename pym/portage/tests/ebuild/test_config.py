# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import portage
from portage import os
from portage.package.ebuild.config import config
from portage.package.ebuild._config.LicenseManager import LicenseManager
from portage.tests import TestCase
from portage.tests.resolver.ResolverPlayground import ResolverPlayground

class ConfigTestCase(TestCase):

	def testFeaturesMutation(self):
		"""
		Test whether mutation of config.features updates the FEATURES
		variable and persists through config.regenerate() calls.
		"""
		playground = ResolverPlayground()
		try:
			settings = config(clone=playground.settings)

			settings.features.add('noclean')
			self.assertEqual('noclean' in settings['FEATURES'].split(), True)
			settings.regenerate()
			self.assertEqual('noclean' in settings['FEATURES'].split(),True)

			settings.features.discard('noclean')
			self.assertEqual('noclean' in settings['FEATURES'].split(), False)
			settings.regenerate()
			self.assertEqual('noclean' in settings['FEATURES'].split(), False)

			settings.features.add('noclean')
			self.assertEqual('noclean' in settings['FEATURES'].split(), True)
			settings.regenerate()
			self.assertEqual('noclean' in settings['FEATURES'].split(),True)
		finally:
			playground.cleanup()

	def testLicenseManager(self):

		user_config = {
			"package.license":
				(
					"dev-libs/* TEST",
					"dev-libs/A -TEST2", 
					"=dev-libs/A-2 TEST3 @TEST",
					"*/* @EULA TEST2",
					"=dev-libs/C-1 *",
					"=dev-libs/C-2 -*",
				),
		}

		playground = ResolverPlayground(user_config=user_config)
		try:
			portage.util.noiselimit = -2

			license_group_locations = (os.path.join(playground.portdir, "profiles"),)
			pkg_license = os.path.join(playground.eroot, "etc", "portage")

			lic_man = LicenseManager(license_group_locations, pkg_license)

			self.assertEqual(lic_man._accept_license_str, None)
			self.assertEqual(lic_man._accept_license, None)
			self.assertEqual(lic_man._license_groups, {"EULA": ["TEST"]})
			self.assertEqual(lic_man._undef_lic_groups, set(["TEST"]))

			self.assertEqual(lic_man.extract_global_changes(), "TEST TEST2")
			self.assertEqual(lic_man.extract_global_changes(), "")

			lic_man.set_accept_license_str("TEST TEST2")
			self.assertEqual(lic_man._getPkgAcceptLicense("dev-libs/B-1", "0"), ["TEST", "TEST2", "TEST"])
			self.assertEqual(lic_man._getPkgAcceptLicense("dev-libs/A-1", "0"), ["TEST", "TEST2", "TEST", "-TEST2"])
			self.assertEqual(lic_man._getPkgAcceptLicense("dev-libs/A-2", "0"), ["TEST", "TEST2", "TEST", "-TEST2", "TEST3", "@TEST"])

			self.assertEqual(lic_man.get_prunned_accept_license("dev-libs/B-1", [], "TEST", "0"), "TEST")
			self.assertEqual(lic_man.get_prunned_accept_license("dev-libs/A-1", [], "-TEST2", "0"), "")
			self.assertEqual(lic_man.get_prunned_accept_license("dev-libs/A-2", [], "|| ( TEST TEST2 )", "0"), "TEST")
			self.assertEqual(lic_man.get_prunned_accept_license("dev-libs/C-1", [], "TEST5", "0"), "TEST5")
			self.assertEqual(lic_man.get_prunned_accept_license("dev-libs/C-2", [], "TEST2", "0"), "")

			self.assertEqual(lic_man.getMissingLicenses("dev-libs/B-1", [], "TEST", "0"), [])
			self.assertEqual(lic_man.getMissingLicenses("dev-libs/A-1", [], "-TEST2", "0"), ["-TEST2"])
			self.assertEqual(lic_man.getMissingLicenses("dev-libs/A-2", [], "|| ( TEST TEST2 )", "0"), [])
			self.assertEqual(lic_man.getMissingLicenses("dev-libs/A-3", [], "|| ( TEST2 || ( TEST3 TEST4 ) )", "0"), ["TEST2", "TEST3", "TEST4"])
			self.assertEqual(lic_man.getMissingLicenses("dev-libs/C-1", [], "TEST5", "0"), [])
			self.assertEqual(lic_man.getMissingLicenses("dev-libs/C-2", [], "TEST2", "0"), ["TEST2"])
			self.assertEqual(lic_man.getMissingLicenses("dev-libs/D-1", [], "", "0"), [])
		finally:
			portage.util.noiselimit = 0
			playground.cleanup()
