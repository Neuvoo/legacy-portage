# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from portage import os
from portage import _python_interpreter
from portage import _shell_quote
from portage.const import EBUILD_SH_BINARY
from portage.package.ebuild.config import config
from portage.package.ebuild.doebuild import spawn as doebuild_spawn
from portage.tests import TestCase
from portage.tests.resolver.ResolverPlayground import ResolverPlayground
from _emerge.EbuildPhase import EbuildPhase
from _emerge.MiscFunctionsProcess import MiscFunctionsProcess
from _emerge.Package import Package
from _emerge.TaskScheduler import TaskScheduler

class DoebuildSpawnTestCase(TestCase):
	"""
	Invoke portage.package.ebuild.doebuild.spawn() with a
	minimal environment. This gives coverage to some of
	the ebuild execution internals, like ebuild.sh,
	AbstractEbuildProcess, and EbuildIpcDaemon.
	"""

	def testDoebuildSpawn(self):
		playground = ResolverPlayground()
		try:
			settings = config(clone=playground.settings)
			cpv = 'sys-apps/portage-2.1'
			metadata = {
				'EAPI'      : '2',
				'INHERITED' : 'python eutils',
				'IUSE'      : 'build doc epydoc python3 selinux',
				'LICENSE'   : 'GPL-2',
				'PROVIDE'   : 'virtual/portage',
				'RDEPEND'   : '>=app-shells/bash-3.2_p17 >=dev-lang/python-2.6',
				'SLOT'      : '0',
			}
			root_config = playground.trees[playground.root]['root_config']
			pkg = Package(built=False, cpv=cpv, installed=False,
				metadata=metadata, root_config=root_config,
				type_name='ebuild')
			settings.setcpv(pkg)
			settings['PORTAGE_PYTHON'] = _python_interpreter
			settings['PORTAGE_BUILDDIR'] = os.path.join(
				settings['PORTAGE_TMPDIR'], cpv)
			settings['T'] = os.path.join(
				settings['PORTAGE_BUILDDIR'], 'temp')
			for x in ('PORTAGE_BUILDDIR', 'T'):
				os.makedirs(settings[x])
			# Create a fake environment, to pretend as if the ebuild
			# has been sourced already.
			open(os.path.join(settings['T'], 'environment'), 'wb')

			task_scheduler = TaskScheduler()
			for phase in ('_internal_test',):

				# Test EbuildSpawnProcess by calling doebuild.spawn() with
				# returnpid=False. This case is no longer used by portage
				# internals since EbuildPhase is used instead and that passes
				# returnpid=True to doebuild.spawn().
				rval = doebuild_spawn("%s %s" % (_shell_quote(
					os.path.join(settings["PORTAGE_BIN_PATH"],
					os.path.basename(EBUILD_SH_BINARY))), phase),
					settings, free=1)
				self.assertEqual(rval, os.EX_OK)

				ebuild_phase = EbuildPhase(background=False,
					phase=phase, scheduler=task_scheduler.sched_iface,
					settings=settings)
				task_scheduler.add(ebuild_phase)
				task_scheduler.run()
				self.assertEqual(ebuild_phase.returncode, os.EX_OK)

			ebuild_phase = MiscFunctionsProcess(background=False,
				commands=['success_hooks'],
				scheduler=task_scheduler.sched_iface, settings=settings)
			task_scheduler.add(ebuild_phase)
			task_scheduler.run()
			self.assertEqual(ebuild_phase.returncode, os.EX_OK)
		finally:
			playground.cleanup()
