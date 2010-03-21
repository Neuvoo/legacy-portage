# test_HookDirectory.py -- Portage Unit Testing Functionality
# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

from portage import os
from portage.hooks import HookDirectory
from portage.package.ebuild.config import config
from portage.tests import TestCase
from tempfile import mkdtemp

class HookDirectoryTestCase(TestCase):
	
	def testHookDirectory(self):
		"""
		Tests to be sure a hook loads and reads the right settings
		Based on test_PackageKeywordsFile.py
		"""

		tmp_dir = self.BuildTmp()
		try:
			settings = config()
			settings["PORTAGE_CONFIGROOT"] = tmp_dir
			hooks = HookDirectory('test', settings)
			hooks.execute()
		finally:
			self.NukeTmp(tmp_dir)
	
	def BuildTmp(self):
		tmp_dir = mkdtemp()
		hooks_dir = tmp_dir+'/etc'
		os.mkdir(hooks_dir)
		hooks_dir = hooks_dir+'/portage'
		os.mkdir(hooks_dir)
		hooks_dir = hooks_dir+'/hooks'
		os.mkdir(hooks_dir)
		hooks_dir = hooks_dir+'/test.d'
		os.mkdir(hooks_dir)
		
		f = open(hooks_dir+'/testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('exit 0\n')
		f.close()
		
		return tmp_dir

	def NukeTmp(self, tmp_dir):
		hooks_dir = tmp_dir+'/etc/portage/hooks/test.d'
		os.unlink(hooks_dir+'/testhook')
		os.rmdir(tmp_dir+'/etc/portage/hooks/test.d')
		os.rmdir(tmp_dir+'/etc/portage/hooks')
		os.rmdir(tmp_dir+'/etc/portage')
		os.rmdir(tmp_dir+'/etc')
		os.rmdir(tmp_dir)
