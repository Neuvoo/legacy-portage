# Copyright 1999-2009 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import re
import sys
from itertools import chain
import portage
from portage.cache.mappings import slot_dict_class
from portage.dep import isvalidatom, paren_reduce, use_reduce, \
	paren_normalize, paren_enclose, _slot_re
from _emerge.Task import Task

if sys.hexversion >= 0x3000000:
	basestring = str
	long = int

class Package(Task):

	__hash__ = Task.__hash__
	__slots__ = ("built", "cpv", "depth",
		"installed", "metadata", "onlydeps", "operation",
		"root_config", "type_name",
		"category", "counter", "cp", "cpv_split",
		"inherited", "invalid", "iuse", "masks", "mtime",
		"pf", "pv_split", "root", "slot", "slot_atom", "visible",) + \
	("_raw_metadata", "_use",)

	metadata_keys = [
		"BUILD_TIME", "CHOST", "COUNTER", "DEPEND", "EAPI",
		"INHERITED", "IUSE", "KEYWORDS",
		"LICENSE", "PDEPEND", "PROVIDE", "RDEPEND",
		"repository", "PROPERTIES", "RESTRICT", "SLOT", "USE",
		"_mtime_", "DEFINED_PHASES"]

	def __init__(self, **kwargs):
		Task.__init__(self, **kwargs)
		self.root = self.root_config.root
		self._raw_metadata = _PackageMetadataWrapperBase(self.metadata)
		self.metadata = _PackageMetadataWrapper(self, self._raw_metadata)
		if not self.built:
			self.metadata['CHOST'] = self.root_config.settings.get('CHOST', '')
		self.cp = portage.cpv_getkey(self.cpv)
		slot = self.slot
		if _slot_re.match(slot) is None:
			self._invalid_metadata('SLOT.invalid',
				"SLOT: invalid value: '%s'" % slot)
			# Avoid an InvalidAtom exception when creating slot_atom.
			# This package instance will be masked due to empty SLOT.
			slot = '0'
		self.slot_atom = portage.dep.Atom("%s:%s" % (self.cp, slot))
		self.category, self.pf = portage.catsplit(self.cpv)
		self.cpv_split = portage.catpkgsplit(self.cpv)
		self.pv_split = self.cpv_split[1:]
		self.masks = self._masks()
		self.visible = self._visible(self.masks)

	def copy(self):
		return Package(built=self.built, cpv=self.cpv, depth=self.depth,
			installed=self.installed, metadata=self._raw_metadata,
			onlydeps=self.onlydeps, operation=self.operation,
			root_config=self.root_config, type_name=self.type_name)

	def _masks(self):
		masks = {}
		settings = self.root_config.settings

		if self.invalid is not None:
			masks['invalid'] = self.invalid

		if not settings._accept_chost(self.cpv, self.metadata):
			masks['CHOST'] = self.metadata['CHOST']

		eapi = self.metadata["EAPI"]
		if not portage.eapi_is_supported(eapi):
			masks['EAPI.unsupported'] = eapi
		if portage._eapi_is_deprecated(eapi):
			masks['EAPI.deprecated'] = eapi

		missing_keywords = settings._getMissingKeywords(
			self.cpv, self.metadata)
		if missing_keywords:
			masks['KEYWORDS'] = missing_keywords

		try:
			missing_properties = settings._getMissingProperties(
				self.cpv, self.metadata)
			if missing_properties:
				masks['PROPERTIES'] = missing_properties
		except portage.exception.InvalidDependString:
			# already recorded as 'invalid'
			pass

		mask_atom = settings._getMaskAtom(self.cpv, self.metadata)
		if mask_atom is not None:
			masks['package.mask'] = mask_atom

		system_mask = settings._getProfileMaskAtom(
			self.cpv, self.metadata)
		if system_mask is not None:
			masks['profile.system'] = system_mask

		try:
			missing_licenses = settings._getMissingLicenses(
				self.cpv, self.metadata)
			if missing_licenses:
				masks['LICENSE'] = missing_licenses
		except portage.exception.InvalidDependString:
			# already recorded as 'invalid'
			pass

		if not masks:
			masks = None

		return masks

	def _visible(self, masks):

		if masks is not None:

			if 'EAPI.unsupported' in masks:
				return False

			if not self.installed and ( \
				'invalid' in masks or \
				'CHOST' in masks or \
				'EAPI.deprecated' in masks or \
				'KEYWORDS' in masks or \
				'PROPERTIES' in masks):
				return False

			if 'package.mask' in masks or \
				'profile.system' in masks or \
				'LICENSE' in masks:
				return False

		return True

	def _invalid_metadata(self, msg_type, msg):
		if self.invalid is None:
			self.invalid = {}
		msgs = self.invalid.get(msg_type)
		if msgs is None:
			msgs = []
			self.invalid[msg_type] = msgs
		msgs.append(msg)

	def __str__(self):
		if self.operation is None:
			self.operation = "merge"
			if self.onlydeps or self.installed:
				self.operation = "nomerge"

		if self.operation == "merge":
			if self.type_name == "binary":
				cpv_color = "PKG_BINARY_MERGE"
			else:
				cpv_color = "PKG_MERGE"
		elif self.operation == "uninstall":
			cpv_color = "PKG_UNINSTALL"
		else:
			cpv_color = "PKG_NOMERGE"

		s = "(%s, %s" \
			% (portage.output.colorize(cpv_color, self.cpv) , self.type_name)

		if self.type_name == "installed":
			if self.root != "/":
				s += " in '%s'" % self.root
			if self.operation == "uninstall":
				s += " scheduled for uninstall"
		else:
			if self.operation == "merge":
				s += " scheduled for merge"
				if self.root != "/":
					s += " to '%s'" % self.root
		s += ")"
		return s

	class _use_class(object):

		__slots__ = ("__weakref__", "enabled")

		def __init__(self, use):
			self.enabled = frozenset(use)

	@property
	def use(self):
		if self._use is None:
			self._use = self._use_class(self.metadata['USE'].split())
		return self._use

	class _iuse(object):

		__slots__ = ("__weakref__", "all", "enabled", "disabled",
			"tokens") + ("_iuse_implicit_regex",)

		def __init__(self, tokens, iuse_implicit_regex):
			self.tokens = tuple(tokens)
			self._iuse_implicit_regex = iuse_implicit_regex
			enabled = []
			disabled = []
			other = []
			for x in tokens:
				prefix = x[:1]
				if prefix == "+":
					enabled.append(x[1:])
				elif prefix == "-":
					disabled.append(x[1:])
				else:
					other.append(x)
			self.enabled = frozenset(enabled)
			self.disabled = frozenset(disabled)
			self.all = frozenset(chain(enabled, disabled, other))

		def is_valid_flag(self, flags):
			"""
			@returns: True if all flags are valid USE values which may
				be specified in USE dependencies, False otherwise.
			"""
			if isinstance(flags, basestring):
				flags = [flags]
			missing_iuse = []
			for flag in flags:
				if not flag in self.all and \
					self._iuse_implicit_regex.match(flag) is None:
					return False
			return True
		
		def get_missing_iuse(self, flags):
			"""
			@returns: A list of flags missing from IUSE.
			"""
			if isinstance(flags, basestring):
				flags = [flags]
			missing_iuse = []
			for flag in flags:
				if not flag in self.all and \
					self._iuse_implicit_regex.match(flag) is None:
					missing_iuse.append(flag)
			return missing_iuse

	def _get_hash_key(self):
		hash_key = getattr(self, "_hash_key", None)
		if hash_key is None:
			if self.operation is None:
				self.operation = "merge"
				if self.onlydeps or self.installed:
					self.operation = "nomerge"
			self._hash_key = \
				(self.type_name, self.root, self.cpv, self.operation)
		return self._hash_key

	def __lt__(self, other):
		if other.cp != self.cp:
			return False
		if portage.pkgcmp(self.pv_split, other.pv_split) < 0:
			return True
		return False

	def __le__(self, other):
		if other.cp != self.cp:
			return False
		if portage.pkgcmp(self.pv_split, other.pv_split) <= 0:
			return True
		return False

	def __gt__(self, other):
		if other.cp != self.cp:
			return False
		if portage.pkgcmp(self.pv_split, other.pv_split) > 0:
			return True
		return False

	def __ge__(self, other):
		if other.cp != self.cp:
			return False
		if portage.pkgcmp(self.pv_split, other.pv_split) >= 0:
			return True
		return False

_all_metadata_keys = set(x for x in portage.auxdbkeys \
	if not x.startswith("UNUSED_"))
_all_metadata_keys.update(Package.metadata_keys)
_all_metadata_keys = frozenset(_all_metadata_keys)

_PackageMetadataWrapperBase = slot_dict_class(_all_metadata_keys)

class _PackageMetadataWrapper(_PackageMetadataWrapperBase):
	"""
	Detect metadata updates and synchronize Package attributes.
	"""

	__slots__ = ("_pkg",)
	_wrapped_keys = frozenset(
		["COUNTER", "INHERITED", "IUSE", "SLOT", "USE", "_mtime_"])
	_use_conditional_keys = frozenset(
		['LICENSE', 'PROPERTIES', 'PROVIDE', 'RESTRICT',])

	def __init__(self, pkg, metadata):
		_PackageMetadataWrapperBase.__init__(self)
		self._pkg = pkg
		if not pkg.built:
			# USE is lazy, but we want it to show up in self.keys().
			_PackageMetadataWrapperBase.__setitem__(self, 'USE', '')

		self.update(metadata)

	def __getitem__(self, k):
		v = _PackageMetadataWrapperBase.__getitem__(self, k)
		if k in self._use_conditional_keys:
			if self._pkg.root_config.settings.local_config and '?' in v:
				try:
					v = paren_enclose(paren_normalize(use_reduce(
						paren_reduce(v), uselist=self._pkg.use.enabled)))
				except portage.exception.InvalidDependString:
					# This error should already have been registered via
					# self._pkg._invalid_metadata().
					pass
				else:
					self[k] = v

		elif k == 'USE' and not self._pkg.built:
			if not v:
				# This is lazy because it's expensive.
				pkgsettings = self._pkg.root_config.trees[
					'porttree'].dbapi.doebuild_settings
				pkgsettings.setcpv(self._pkg)
				v = pkgsettings["PORTAGE_USE"]
				_PackageMetadataWrapperBase.__setitem__(self, 'USE', v)

		return v

	def __setitem__(self, k, v):
		_PackageMetadataWrapperBase.__setitem__(self, k, v)
		if k in self._wrapped_keys:
			getattr(self, "_set_" + k.lower())(k, v)
		elif k in self._use_conditional_keys:
			try:
				reduced = use_reduce(paren_reduce(v), matchall=1)
			except portage.exception.InvalidDependString as e:
				self._pkg._invalid_metadata(k + ".syntax", "%s: %s" % (k, e))
			else:
				if reduced and k == 'PROVIDE':
					for x in portage.flatten(reduced):
						if not isvalidatom(x):
							self._pkg._invalid_metadata(k + ".syntax",
								"%s: %s" % (k, x))

	def _set_inherited(self, k, v):
		if isinstance(v, basestring):
			v = frozenset(v.split())
		self._pkg.inherited = v

	def _set_iuse(self, k, v):
		self._pkg.iuse = self._pkg._iuse(
			v.split(), self._pkg.root_config.settings._iuse_implicit_re)

	def _set_slot(self, k, v):
		self._pkg.slot = v

	def _set_counter(self, k, v):
		if isinstance(v, basestring):
			try:
				v = long(v.strip())
			except ValueError:
				v = 0
		self._pkg.counter = v

	def _set_use(self, k, v):
		# Force regeneration of _use attribute
		self._pkg._use = None
		# Use raw metadata to restore USE conditional values
		# to unevaluated state
		raw_metadata = self._pkg._raw_metadata
		for x in self._use_conditional_keys:
			try:
				self[x] = raw_metadata[x]
			except KeyError:
				pass

	def _set__mtime_(self, k, v):
		if isinstance(v, basestring):
			try:
				v = long(v.strip())
			except ValueError:
				v = 0
		self._pkg.mtime = v

	@property
	def properties(self):
		return self['PROPERTIES'].split()

	@property
	def restrict(self):
		return self['RESTRICT'].split()

	@property
	def defined_phases(self):
		return self['DEFINED_PHASES'].split()
