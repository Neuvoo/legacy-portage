#!/usr/bin/python
# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
#
# This is a helper which ebuild processes can use
# to communicate with portage's main python process.

import os
import pickle
import select
import signal
import sys

def debug_signal(signum, frame):
	import pdb
	pdb.set_trace()
signal.signal(signal.SIGUSR1, debug_signal)

# Avoid sandbox violations after python upgrade.
pym_path = os.path.join(os.path.dirname(
	os.path.dirname(os.path.realpath(__file__))), "pym")
if os.environ.get("SANDBOX_ON") == "1":
	sandbox_write = os.environ.get("SANDBOX_WRITE", "").split(":")
	if pym_path not in sandbox_write:
		sandbox_write.append(pym_path)
		os.environ["SANDBOX_WRITE"] = \
			":".join(filter(None, sandbox_write))

import portage

class EbuildIpc(object):

	def __init__(self):
		self.fifo_dir = os.environ['PORTAGE_BUILDDIR']
		self.ipc_in_fifo = os.path.join(self.fifo_dir, '.ipc_in')
		self.ipc_out_fifo = os.path.join(self.fifo_dir, '.ipc_out')
		self.ipc_lock_file = os.path.join(self.fifo_dir, '.ipc_lock')

	def communicate(self, args):
		# Make locks quiet since unintended locking messages displayed on
		# stdout could corrupt the intended output of this program.
		portage.locks._quiet = True
		lock_obj = portage.locks.lockfile(self.ipc_lock_file, unlinkfile=True)
		try:
			return self._communicate(args)
		finally:
			portage.locks.unlockfile(lock_obj)

	def _communicate(self, args):
		input_fd = os.open(self.ipc_out_fifo, os.O_RDONLY|os.O_NONBLOCK)
		input_file = os.fdopen(input_fd, 'rb')
		output_file = open(self.ipc_in_fifo, 'wb')
		pickle.dump(args, output_file)
		output_file.flush()

		events = select.select([input_file], [], [])
		reply = pickle.load(input_file)
		output_file.close()
		input_file.close()

		(out, err, rval) = reply

		if out:
			portage.util.writemsg_stdout(out, noiselevel=-1)

		if err:
			portage.util.writemsg(err, noiselevel=-1)

		return rval

def ebuild_ipc_main(args):
	ebuild_ipc = EbuildIpc()
	return ebuild_ipc.communicate(args)

if __name__ == '__main__':
	sys.exit(ebuild_ipc_main(sys.argv[1:]))
