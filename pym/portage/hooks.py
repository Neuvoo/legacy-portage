# Copyright 1998-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

# TODO: following may be harmful, but helpful for debugging
#import os, sys
#import os.path as osp
#sys.path.insert(0, osp.dirname(osp.dirname(osp.abspath(__file__))))

from portage.const import BASH_BINARY, HOOKS_PATH
from portage import os
from portage import check_config_instance
from portage import normalize_path
from portage.exception import PortageException
from portage.exception import InvalidLocation
from process import spawn

class HookDirectory(object):

	def __init__ (self, phase, settings):
		check_config_instance(settings)
		self.settings = settings
		self.path = os.path.join(settings["PORTAGE_CONFIGROOT"], HOOKS_PATH, phase + '.d')

	def execute (self, path=None):
		if not path:
			path = self.path
		
		path = normalize_path(path)
		
		if not os.path.exists(path):
			raise InvalidLocation('This hooks path could not be found: ' + path)
		
		if os.path.isdir(path):
			for parent, dirs, files in os.walk(path):
				for filename in files:
					if filename[:1] == '.':
						continue
					else:
						self.execute(os.path.join(path, filename))
		
		elif os.path.isfile(path):
			code = spawn(mycommand=[BASH_BINARY, path], env=self.settings.environ())
			if code: # if failure
				raise PortageException('!!! Hook %s failed with exit code %s' % (path, code))

if __name__ == "__main__": # TODO: debug
	from portage.package.ebuild.config import config
	HookDirectory('run', config()).execute()
