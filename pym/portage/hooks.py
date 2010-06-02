# Copyright 1998-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

from portage.const import BASH_BINARY, HOOKS_PATH, PORTAGE_BIN_PATH
from portage import os
from portage import check_config_instance
from portage import normalize_path
from portage.exception import PortageException
from portage.exception import InvalidLocation
from portage.output import EOutput
from process import spawn

class HookDirectory(object):

	def __init__ (self, phase, settings, myopts=None, myaction=None, mytargets=None):
		self.myopts = myopts
		self.myaction = myaction
		self.mytargets = mytargets
		check_config_instance(settings)
		self.settings = settings
		self.path = os.path.join(settings["PORTAGE_CONFIGROOT"], HOOKS_PATH, phase + '.d')
		self.output = EOutput()

	def execute (self, path=None):
		if not path:
			path = self.path
		
		path = normalize_path(path)
		
		if not os.path.exists(path):
			if self.myopts and "--debug" in self.myopts:
				self.output.ewarn('This hook path could not be found; ignored: ' + path)
			return
		
		if os.path.isdir(path):
			for parent, dirs, files in os.walk(path):
				for dir in dirs:
					if self.myopts and "--debug" in self.myopts:
						self.output.ewarn('Directory within hook directory not allowed; ignored: ' + path+'/'+dir)
				for filename in files:
					HookFile(os.path.join(path, filename), self.settings, self.myopts, self.myaction, self.mytargets).execute()
		
		else:
			raise InvalidLocation('This hook path ought to be a directory: ' + path)

class HookFile (object):
	
	def __init__ (self, path, settings, myopts=None, myaction=None, mytargets=None):
		self.myopts = myopts
		self.myaction = myaction
		self.mytargets = mytargets
		check_config_instance(settings)
		self.path = normalize_path(path)
		self.settings = settings
		self.output = EOutput()
	
	def execute (self):
		if "hooks" not in self.settings['FEATURES']:
			return
		
		if not os.path.exists(self.path):
			raise InvalidLocation('This hook path could not be found: ' + self.path)
		
		if os.path.isfile(self.path):
			command=[self.path]
			if self.myopts:
				for myopt in self.myopts:
					command.extend(['--opt', myopt])
			if self.myaction:
				command.extend(['--action', self.myaction])
			if self.mytargets:
				for mytarget in self.mytargets:
					command.extend(['--target', mytarget])
			
			command=[BASH_BINARY, '-c', 'source ' + PORTAGE_BIN_PATH + '/isolated-functions.sh && source ' + ' '.join(command)]
			if self.myopts and "--verbose" in self.myopts:
				self.output.einfo('Executing hook "' + self.path + '"...')
			code = spawn(mycommand=command, env=self.settings.environ())
			if code: # if failure
				raise PortageException('!!! Hook %s failed with exit code %s' % (self.path, code))
		
		else:
			raise InvalidLocation('This hook path ought to be a file: ' + self.path)
