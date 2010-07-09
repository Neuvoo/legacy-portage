# Copyright 1998-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

from portage.const import BASH_BINARY, HOOKS_PATH, HOOKS_SH_BINARY, PORTAGE_BIN_PATH
from portage import os
from portage import check_config_instance
from portage import normalize_path
from portage.exception import PortageException
from portage.exception import InvalidLocation
from portage.output import EOutput
from process import spawn
from shutil import rmtree
from tempfile import mkdtemp

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
		if "hooks" not in self.settings['FEATURES']:
			return
		
		if not path:
			path = self.path
		
		path = normalize_path(path)
		
		if not os.path.exists(path):
			if self.myopts and "--debug" in self.myopts:
				# behavior mimicked by hook.sh
				self.output.ewarn('This hook path could not be found; ignored: ' + path)
			return
		
		if os.path.isdir(path):
			command=[HOOKS_SH_BINARY]
			if self.myopts:
				for myopt in self.myopts:
					command.extend(['--opt', myopt])
			if self.myaction:
				command.extend(['--action', self.myaction])
			if self.mytargets:
				for mytarget in self.mytargets:
					command.extend(['--target', mytarget])
			
			command=[BASH_BINARY, '-c', 'cd "'+path+'" && source "' + PORTAGE_BIN_PATH + '/isolated-functions.sh" && source ' + ' '.join(command)]
			if self.myopts and "--verbose" in self.myopts:
				self.output.einfo('Executing hooks directory "' + self.path + '"...')
			code = spawn(mycommand=command, env=self.settings.environ())
			if code: # if failure
				# behavior mimicked by hook.sh
				raise PortageException('!!! Hook directory %s failed with exit code %s' % (self.path, code))
		
		else:
			raise InvalidLocation('This hook path ought to be a directory: ' + path)
	
	def merge_to_env (self, existingenv, path):
		path = normalize_path(path)

		if not os.path.isdir(path):
			raise InvalidLocation('This environment path is not a directory: ' + path)
		
		for parent, dirs, files in os.walk(path):
			for varname in files:
				file = open(os.path.join(path, varname), 'r')
				# read the file, remove the very last newline, and make the escaped double-quotes just plain double-quotes (since only bash needs them to be escaped, not python)
				vardata = file.read()[:-1].replace('\"','"').strip('"')
				existingenv[varname] = vardata
				existingenv.backup_changes(varname)
		
		return existingenv
