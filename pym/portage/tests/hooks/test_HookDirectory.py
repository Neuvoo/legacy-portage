# test_HookDirectory.py -- Portage Unit Testing Functionality
# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

from portage import os
from portage.hooks import HookDirectory
from portage.package.ebuild.config import config
from portage.tests import TestCase
from tempfile import mkdtemp
from shutil import rmtree

class HookDirectoryTestCase(TestCase):
	
	def testHookDirectory(self):
		"""
		Tests to be sure a hook loads and reads the right settings
		Based on test_PackageKeywordsFile.py
		"""

		self.tmp_dir_path = self.BuildTmp('/etc/portage/hooks/test.d')
		try:
			settings = config()
			settings["PORTAGE_CONFIGROOT"] = self.tmp_dir_path
			settings["FEATURES"] += " hooks"
			hooks = HookDirectory(phase='test', settings=settings)
			hooks.execute()
			self.assert_(settings["hookonlytest"] == "")
		finally:
			rmtree(self.tmp_dir_path)
	
	def BuildTmp(self, tmp_subdir):
		tmp_dir = mkdtemp()
		hooks_dir = tmp_dir + '/' + tmp_subdir
		os.makedirs(hooks_dir)
		
		f = open(hooks_dir+'/1-testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('export hookonlytest="portage cannot see me!"\n')
		f.write('exit 0\n')
		f.close()
		
		f = open(hooks_dir+'/2-testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('if [[ "${hookonlytest}" != "" ]]; then echo "Unexpected hookonlytest value: ${hookonlytest}"; exit 1; fi\n');
		f.write('exit 0\n')
		f.close()
		
		return tmp_dir
