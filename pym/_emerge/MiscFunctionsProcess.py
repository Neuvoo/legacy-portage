# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from _emerge.AbstractEbuildProcess import AbstractEbuildProcess
import portage
portage.proxy.lazyimport.lazyimport(globals(),
	'portage.package.ebuild.doebuild:spawn'
)
from portage import os

class MiscFunctionsProcess(AbstractEbuildProcess):
	"""
	Spawns misc-functions.sh with an existing ebuild environment.
	"""

	__slots__ = ('commands',)

	def _start(self):
		settings = self.settings
		portage_bin_path = settings["PORTAGE_BIN_PATH"]
		misc_sh_binary = os.path.join(portage_bin_path,
			os.path.basename(portage.const.MISC_SH_BINARY))

		self.args = [portage._shell_quote(misc_sh_binary)] + self.commands
		if self.logfile is None:
			self.logfile = settings.get("PORTAGE_LOG_FILE")

		AbstractEbuildProcess._start(self)

	def _spawn(self, args, **kwargs):
		self.settings.pop("EBUILD_PHASE", None)
		return spawn(" ".join(args), self.settings, **kwargs)
