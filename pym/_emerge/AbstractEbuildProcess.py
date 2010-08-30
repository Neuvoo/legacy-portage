# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import stat
import textwrap
from _emerge.SpawnProcess import SpawnProcess
from _emerge.EbuildIpcDaemon import EbuildIpcDaemon
import portage
from portage.elog.messages import eerror
from portage.localization import _
from portage.package.ebuild._ipc.ExitCommand import ExitCommand
from portage.package.ebuild._ipc.QueryCommand import QueryCommand
from portage import os
from portage import StringIO
from portage import _encodings
from portage import _unicode_decode
from portage.util._pty import _create_pty_or_pipe
from portage.util import apply_secpass_permissions

class AbstractEbuildProcess(SpawnProcess):

	__slots__ = ('phase', 'settings',) + \
		('_ipc_daemon', '_exit_command',)
	_phases_without_builddir = ('clean', 'cleanrm', 'depend', 'help',)

	# Number of milliseconds to allow natural exit of the ebuild
	# process after it has called the exit command via IPC. It
	# doesn't hurt to be generous here since the scheduler
	# continues to process events during this period, and it can
	# return long before the timeout expires.
	_exit_timeout = 10000 # 10 seconds

	# The EbuildIpcDaemon support is well tested, but this variable
	# is left so we can temporarily disable it if any issues arise.
	_enable_ipc_daemon = True

	def __init__(self, **kwargs):
		SpawnProcess.__init__(self, **kwargs)
		if self.phase is None:
			phase = self.settings.get("EBUILD_PHASE")
			if not phase:
				phase = 'other'
			self.phase = phase

	def _start(self):

		if self.background:
			# Automatically prevent color codes from showing up in logs,
			# since we're not displaying to a terminal anyway.
			self.settings['NOCOLOR'] = 'true'

		if self._enable_ipc_daemon:
			self.settings.pop('PORTAGE_EBUILD_EXIT_FILE', None)
			if self.phase not in self._phases_without_builddir:
				self.settings['PORTAGE_IPC_DAEMON'] = "1"
				self._start_ipc_daemon()
			else:
				self.settings.pop('PORTAGE_IPC_DAEMON', None)
		else:
			# Since the IPC daemon is disabled, use a simple tempfile based
			# approach to detect unexpected exit like in bug #190128.
			self.settings.pop('PORTAGE_IPC_DAEMON', None)
			if self.phase not in self._phases_without_builddir:
				exit_file = os.path.join(
					self.settings['PORTAGE_BUILDDIR'],
					'.exit_status')
				self.settings['PORTAGE_EBUILD_EXIT_FILE'] = exit_file
				try:
					os.unlink(exit_file)
				except OSError:
					if os.path.exists(exit_file):
						# make sure it doesn't exist
						raise
			else:
				self.settings.pop('PORTAGE_EBUILD_EXIT_FILE', None)

		SpawnProcess._start(self)

	def _init_ipc_fifos(self):

		input_fifo = os.path.join(
			self.settings['PORTAGE_BUILDDIR'], '.ipc_in')
		output_fifo = os.path.join(
			self.settings['PORTAGE_BUILDDIR'], '.ipc_out')

		for p in (input_fifo, output_fifo):

			st = None
			try:
				st = os.lstat(p)
			except OSError:
				os.mkfifo(p)
			else:
				if not stat.S_ISFIFO(st.st_mode):
					st = None
					try:
						os.unlink(p)
					except OSError:
						pass
					os.mkfifo(p)

			apply_secpass_permissions(p,
				uid=os.getuid(),
				gid=portage.data.portage_gid,
				mode=0o770, stat_cached=st)

		return (input_fifo, output_fifo)

	def _start_ipc_daemon(self):
		self._exit_command = ExitCommand()
		self._exit_command.reply_hook = self._exit_command_callback
		query_command = QueryCommand(self.settings)
		commands = {
			'best_version' : query_command,
			'exit'         : self._exit_command,
			'has_version'  : query_command,
		}
		input_fifo, output_fifo = self._init_ipc_fifos()
		self._ipc_daemon = EbuildIpcDaemon(commands=commands,
			input_fifo=input_fifo,
			output_fifo=output_fifo,
			scheduler=self.scheduler)
		self._ipc_daemon.start()

	def _exit_command_callback(self):
		if self._registered:
			# Let the process exit naturally, if possible.
			self.scheduler.schedule(self._reg_id, timeout=self._exit_timeout)
			if self._registered:
				# If it doesn't exit naturally in a reasonable amount
				# of time, kill it (solves bug #278895). We try to avoid
				# this when possible since it makes sandbox complain about
				# being killed by a signal.
				self.cancel()

	def _orphan_process_warn(self):
		phase = self.phase

		msg = _("The ebuild phase '%s' with pid %s appears "
		"to have left an orphan process running in the "
		"background.") % (phase, self.pid)

		self._eerror(textwrap.wrap(msg, 72))

	def _pipe(self, fd_pipes):
		stdout_pipe = fd_pipes.get(1)
		got_pty, master_fd, slave_fd = \
			_create_pty_or_pipe(copy_term_size=stdout_pipe)
		return (master_fd, slave_fd)

	def _can_log(self, slave_fd):
		# With sesandbox, logging works through a pty but not through a
		# normal pipe. So, disable logging if ptys are broken.
		# See Bug #162404.
		# TODO: Add support for logging via named pipe (fifo) with
		# sesandbox, since EbuildIpcDaemon uses a fifo and it's known
		# to be compatible with sesandbox.
		return not ('sesandbox' in self.settings.features \
			and self.settings.selinux_enabled()) or os.isatty(slave_fd)

	def _unexpected_exit(self):

		phase = self.phase

		msg = _("The ebuild phase '%s' has exited "
		"unexpectedly. This type of behavior "
		"is known to be triggered "
		"by things such as failed variable "
		"assignments (bug #190128) or bad substitution "
		"errors (bug #200313). Normally, before exiting, bash should "
		"have displayed an error message above. If bash did not "
		"produce an error message above, it's possible "
		"that the ebuild has called `exit` when it "
		"should have called `die` instead. This behavior may also "
		"be triggered by a corrupt bash binary or a hardware "
		"problem such as memory or cpu malfunction. If the problem is not "
		"reproducible or it appears to occur randomly, then it is likely "
		"to be triggered by a hardware problem. "
		"If you suspect a hardware problem then you should "
		"try some basic hardware diagnostics such as memtest. "
		"Please do not report this as a bug unless it is consistently "
		"reproducible and you are sure that your bash binary and hardware "
		"are functioning properly.") % phase

		self._eerror(textwrap.wrap(msg, 72))

	def _eerror(self, lines):
		out = StringIO()
		phase = self.phase
		for line in lines:
			eerror(line, phase=phase, key=self.settings.mycpv, out=out)
		msg = _unicode_decode(out.getvalue(),
			encoding=_encodings['content'], errors='replace')
		if msg:
			self.scheduler.output(msg,
				log_path=self.settings.get("PORTAGE_LOG_FILE"))

	def _set_returncode(self, wait_retval):
		SpawnProcess._set_returncode(self, wait_retval)

		if self._ipc_daemon is not None:
			self._ipc_daemon.cancel()
			if self._exit_command.exitcode is not None:
				self.returncode = self._exit_command.exitcode
			else:
				self.returncode = 1
				self._unexpected_exit()
		else:
			exit_file = self.settings.get('PORTAGE_EBUILD_EXIT_FILE')
			if exit_file and not os.path.exists(exit_file):
				self.returncode = 1
				self._unexpected_exit()
