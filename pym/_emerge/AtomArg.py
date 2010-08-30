# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from _emerge.DependencyArg import DependencyArg

class AtomArg(DependencyArg):
	def __init__(self, atom=None, **kwargs):
		DependencyArg.__init__(self, **kwargs)
		self.atom = atom
		self.set = (self.atom, )
