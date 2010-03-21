# Copyright 1998-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

# TODO: following may be harmful, but helpful for debugging
#import os, sys
#import os.path as osp
#sys.path.insert(0, osp.dirname(osp.dirname(osp.abspath(__file__))))

from portage.const import BASH_BINARY, HOOKS_PATH, PORTAGE_BIN_PATH
from portage import os
from portage import check_config_instance
from portage import normalize_path
from portage.exception import PortageException
from portage.exception import InvalidLocation
from portage.output import EOutput
from process import spawn

class HookDirectory(object):

	def __init__ (self, phase, settings, myopts=None, myaction=None, myfiles=None):
		self.myopts = myopts
		self.myaction = myaction
		self.myfiles = myfiles
		check_config_instance(settings)
		self.settings = settings
		self.path = os.path.join(settings["PORTAGE_CONFIGROOT"], HOOKS_PATH, phase + '.d')
		self.output = EOutput()

	def execute (self, path=None):
		if not path:
			path = self.path
		
		path = normalize_path(path)
		
		if not os.path.exists(path):
			self.output.ewarn('This hook path could not be found: ' + path)
			return
		
		if os.path.isdir(path):
			for parent, dirs, files in os.walk(path):
				for dir in dirs:
					self.output.ewarn('Directory within hook directory not allowed: ' + path+'/'+dir)
				for filename in files:
					HookFile(os.path.join(path, filename), self.settings, self.myopts, self.myaction, self.myfiles).execute()
		
		else:
			raise InvalidLocation('This hook path ought to be a directory: ' + path)

class HookFile (object):
	
	def __init__ (self, path, settings, myopts=None, myaction=None, myfiles=None):
		self.myopts = myopts
		self.myaction = myaction
		self.myfiles = myfiles
		check_config_instance(settings)
		self.path = path
		self.settings = settings
	
	def execute (self):
		path = normalize_path(self.path)
		
		if not os.path.exists(path):
			raise InvalidLocation('This hook path could not be found: ' + path)
		
		if os.path.isfile(path):
			command=[path]
			if self.myopts:
				for myopt in self.myopts:
					command.extend(['--opt', myopt])
			if self.myaction:
				command.extend(['--action', self.myaction])
			if self.myfiles:
				for myfile in self.myfiles:
					command.extend(['--file', myfile])
			
			command=[BASH_BINARY, '-c', 'source ' + PORTAGE_BIN_PATH + '/isolated-functions.sh && ' + ' '.join(command)]
			code = spawn(mycommand=command, env=self.settings.environ())
			if code: # if failure
				raise PortageException('!!! Hook %s failed with exit code %s' % (path, code))
		
		else:
			raise InvalidLocation('This hook path ought to be a file: ' + path)

if __name__ == "__main__": # TODO: debug
	from portage.package.ebuild.config import config
	HookDirectory('run', config()).execute()
