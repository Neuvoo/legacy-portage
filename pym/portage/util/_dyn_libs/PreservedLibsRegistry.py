# Copyright 1998-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import errno
import logging

try:
	import cPickle as pickle
except ImportError:
	import pickle

from portage import os
from portage import _encodings
from portage import _os_merge
from portage import _unicode_encode
from portage.exception import PermissionDenied
from portage.localization import _
from portage.util import atomic_ofstream
from portage.util import writemsg_level
from portage.versions import cpv_getkey

class PreservedLibsRegistry(object):
	""" This class handles the tracking of preserved library objects """
	def __init__(self, eroot, filename, autocommit=True):
		""" 
			@param eroot: root used to check existence of paths in pruneNonExisting
		    @type eroot: String
			@param filename: absolute path for saving the preserved libs records
		    @type filename: String
			@param autocommit: determines if the file is written after every update
			@type autocommit: Boolean
		"""
		self._eroot = eroot
		self._filename = filename
		self._autocommit = autocommit
		self.load()
		self.pruneNonExisting()

	def load(self):
		""" Reload the registry data from file """
		self._data = None
		try:
			self._data = pickle.load(
				open(_unicode_encode(self._filename,
					encoding=_encodings['fs'], errors='strict'), 'rb'))
		except (ValueError, pickle.UnpicklingError) as e:
			writemsg_level(_("!!! Error loading '%s': %s\n") % \
				(self._filename, e), level=logging.ERROR, noiselevel=-1)
		except (EOFError, IOError) as e:
			if isinstance(e, EOFError) or e.errno == errno.ENOENT:
				pass
			elif e.errno == PermissionDenied.errno:
				raise PermissionDenied(self._filename)
			else:
				raise
		if self._data is None:
			self._data = {}
		self._data_orig = self._data.copy()
	def store(self):
		""" Store the registry data to file. No need to call this if autocommit
		    was enabled.
		"""
		if os.environ.get("SANDBOX_ON") == "1" or \
			self._data == self._data_orig:
			return
		try:
			f = atomic_ofstream(self._filename, 'wb')
			pickle.dump(self._data, f, protocol=2)
			f.close()
		except EnvironmentError as e:
			if e.errno != PermissionDenied.errno:
				writemsg_level("!!! %s %s\n" % (e, self._filename),
					level=logging.ERROR, noiselevel=-1)
		else:
			self._data_orig = self._data.copy()

	def register(self, cpv, slot, counter, paths):
		""" Register new objects in the registry. If there is a record with the
			same packagename (internally derived from cpv) and slot it is 
			overwritten with the new data.
			@param cpv: package instance that owns the objects
			@type cpv: CPV (as String)
			@param slot: the value of SLOT of the given package instance
			@type slot: String
			@param counter: vdb counter value for the package instace
			@type counter: Integer
			@param paths: absolute paths of objects that got preserved during an update
			@type paths: List
		"""
		cp = cpv_getkey(cpv)
		cps = cp+":"+slot
		if len(paths) == 0 and cps in self._data \
				and self._data[cps][0] == cpv and int(self._data[cps][1]) == int(counter):
			del self._data[cps]
		elif len(paths) > 0:
			self._data[cps] = (cpv, counter, paths)
		if self._autocommit:
			self.store()
	
	def unregister(self, cpv, slot, counter):
		""" Remove a previous registration of preserved objects for the given package.
			@param cpv: package instance whose records should be removed
			@type cpv: CPV (as String)
			@param slot: the value of SLOT of the given package instance
			@type slot: String
		"""
		self.register(cpv, slot, counter, [])
	
	def pruneNonExisting(self):
		""" Remove all records for objects that no longer exist on the filesystem. """

		os = _os_merge

		for cps in list(self._data):
			cpv, counter, paths = self._data[cps]
			paths = [f for f in paths \
				if os.path.exists(os.path.join(self._eroot, f.lstrip(os.sep)))]
			if len(paths) > 0:
				self._data[cps] = (cpv, counter, paths)
			else:
				del self._data[cps]
		if self._autocommit:
			self.store()
	
	def hasEntries(self):
		""" Check if this registry contains any records. """
		return len(self._data) > 0
	
	def getPreservedLibs(self):
		""" Return a mapping of packages->preserved objects.
			@returns mapping of package instances to preserved objects
			@rtype Dict cpv->list-of-paths
		"""
		rValue = {}
		for cps in self._data:
			rValue[self._data[cps][0]] = self._data[cps][2]
		return rValue
