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

# http://stackoverflow.com/questions/845058/how-to-get-line-count-cheaply-in-python
def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i + 1

class HookDirectoryTestCase(TestCase):
	
	def testHookDirectory(self):
		"""
		Tests to be sure a hook loads and reads the right settings
		Based on test_PackageKeywordsFile.py
		"""

		tmp_dir_path = self.BuildTmp('/etc/portage/hooks/test.d')
		try:
			settings = config()
			settings["PORTAGE_CONFIGROOT"] = tmp_dir_path
			settings["FEATURES"] += " hooks"
			hooks = HookDirectory('test', settings)
			hooks.execute()
			self.assert_(settings["test"] == "this is a test")
			self.assert_(file_len(tmp_dir_path+'/output') == 1)
		finally:
			rmtree(tmp_dir_path)
	
	def BuildTmp(self, tmp_subdir):
		tmp_dir = mkdtemp()
		hooks_dir = tmp_dir + '/' + tmp_subdir
		os.makedirs(hooks_dir)
		
		f = open(hooks_dir+'/testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('test="this is a test"\n')
		f.write('echo hi > '+tmp_dir+'/output && hooksave test && exit 0\n')
		f.close()
		
		return tmp_dir
