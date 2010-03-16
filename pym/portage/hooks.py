# Copyright 1998-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

# TODO: following may be harmful, but helpful for debugging
import os, sys
import os.path as osp
sys.path.insert(0, osp.dirname(osp.dirname(osp.abspath(__file__))))

from portage.const import BASH_BINARY, HOOKS_PATH
from portage import os
from portage import check_config_instance
from process import spawn

class hooks(object):

	def __init__ (self, phase, settings):
		check_config_instace(settings)
		self.settings = settings
		self.path = os.path.join(HOOKS_PATH, phase + ".d")

	def execute (self):
		if not path:
			path = self.path
			
		path = normalize_path(path)
		
		if os.path.isdir(path):
			for parent, dirs, files in os.walk(path):
				for filename in files:
					if filename[:1] == '.':
						continue
					self.execute(os.path.join(path, filename))
		
		elif os.path.isfile(path):
			code = spawn(mycommand=[BASH_BINARY, path], env=mysettings.environ())
			if code: # if failure
				raise portage.exception.PortageException("!!! Hook %s failed with exit code %s" % (path, code))
