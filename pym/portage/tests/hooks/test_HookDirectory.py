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

		tmp_dirs = ['etc', 'portage', 'hooks', 'test.d']
		tmp_dir_path = self.BuildTmp(tmp_dirs)
		tmp_dirs = [tmp_dir_path, 'etc', 'portage', 'hooks', 'test.d']
		try:
			settings = config()
			settings["PORTAGE_CONFIGROOT"] = tmp_dir_path
			hooks = HookDirectory('test', settings)
			hooks.execute()
		finally:
			self.NukeTmp(tmp_dirs)
	
	def BuildTmp(self, tmp_subdirs):
		tmp_dir_path = mkdtemp()
		hooks_dir = tmp_dir_path
		for tmp_subdir in tmp_subdirs:
			hooks_dir = hooks_dir + '/' + tmp_subdir
			os.mkdir(hooks_dir)
		
		f = open(hooks_dir+'/testhook', 'w')
		f.write('#!/bin/bash\n')
		f.write('exit 0\n')
		f.close()
		
		return tmp_dir_path

	def NukeTmp(self, tmp_dirs):
		tmp_dir_paths = []
		curr_path = ''
		for tmp_dir in tmp_dirs:
			curr_path = curr_path + '/' + tmp_dir
			tmp_dir_paths.append(curr_path)
		
		tmp_dir_paths.reverse()
		os.unlink(curr_path+'/testhook')
		for tmp_dir_path in tmp_dir_paths:
			os.rmdir(tmp_dir_path)
