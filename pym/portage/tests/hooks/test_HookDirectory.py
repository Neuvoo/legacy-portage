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

		self.tmp_dir_path = self.BuildTmp('/etc/portage/hooks/test.d')
		try:
			settings = config()
			settings["PORTAGE_CONFIGROOT"] = self.tmp_dir_path
			settings["FEATURES"] += " hooks"
			hooks = HookDirectory(phase='test', settings=settings)
			hooks.execute()
			self.assert_(settings["test"] == "this is another test")
			self.assert_(settings["test2"] == "this is a second test")
			self.assert_(settings["hookonlytest"] == "")
			self.assert_(file_len(self.tmp_dir_path+'/output') == 2)
		finally:
			rmtree(self.tmp_dir_path)
	
	def BuildTmp(self, tmp_subdir):
		tmp_dir = mkdtemp()
		hooks_dir = tmp_dir + '/' + tmp_subdir
		os.makedirs(hooks_dir)
		
		f = open(hooks_dir+'/1-testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('test="this is a test"\n')
		f.write('hookonlytest="portage cannot see me!"\n')
		f.write('echo hi >> '+tmp_dir+'/output && hooks_savesetting test && hooks_saveenvonly hookonlytest\n')
		f.write('exit $?\n')
		f.close()
		
		f = open(hooks_dir+'/2-testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('if [[ "${test}" != "this is a test" ]]; then echo "Unexpected test value: ${test}"; exit 3; fi\n');
		f.write('if [[ "${hookonlytest}" != "portage cannot see me!" ]]; then echo "Unexpected hookonlytest value: ${hookonlytest}"; exit 3; fi\n');
		f.write('test="this is another test"\n')
		f.write('test2="this is a second test"\n')
		f.write('echo hey >> '+tmp_dir+'/output && hooks_savesetting test && hooks_savesetting test2\n')
		f.write('exit $?\n')
		f.close()
		
		return tmp_dir
