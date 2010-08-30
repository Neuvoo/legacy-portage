# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

from itertools import chain, permutations
import shutil
import tempfile
import portage
from portage import os
from portage.const import PORTAGE_BASE_PATH
from portage.dbapi.vartree import vartree
from portage.dbapi.porttree import portagetree
from portage.dbapi.bintree import binarytree
from portage.dep import Atom
from portage.package.ebuild.config import config
from portage._sets import load_default_config
from portage.versions import catsplit

from _emerge.Blocker import Blocker
from _emerge.create_depgraph_params import create_depgraph_params
from _emerge.depgraph import backtrack_depgraph
from _emerge.RootConfig import RootConfig

class ResolverPlayground(object):
	"""
	This class help to create the necessary files on disk and
	the needed settings instances, etc. for the resolver to do
	it's work.
	"""

	config_files = frozenset(("package.use", "package.mask", "package.keywords", \
		"package.unmask", "package.properties", "package.license"))

	def __init__(self, ebuilds={}, installed={}, profile={}, user_config={}, sets={}, world=[], debug=False):
		"""
		ebuilds: cpv -> metadata mapping simulating avaiable ebuilds. 
		installed: cpv -> metadata mapping simulating installed packages.
			If a metadata key is missing, it gets a default value.
		profile: settings defined by the profile.
		"""
		self.debug = debug
		self.root = "/"
		self.eprefix = tempfile.mkdtemp()
		self.eroot = self.root + self.eprefix.lstrip(os.sep) + os.sep
		self.portdir = os.path.join(self.eroot, "usr/portage")
		self.vdbdir = os.path.join(self.eroot, "var/db/pkg")
		os.makedirs(self.portdir)
		os.makedirs(self.vdbdir)

		if not debug:
			portage.util.noiselimit = -2

		self._create_ebuilds(ebuilds)
		self._create_installed(installed)
		self._create_profile(ebuilds, installed, profile, user_config, sets)
		self._create_world(world)

		self.settings, self.trees = self._load_config()

		self._create_ebuild_manifests(ebuilds)
		
		portage.util.noiselimit = 0

	def _create_ebuilds(self, ebuilds):
		for cpv in ebuilds:
			a = Atom("=" + cpv)
			ebuild_dir = os.path.join(self.portdir, a.cp)
			ebuild_path = os.path.join(ebuild_dir, a.cpv.split("/")[1] + ".ebuild")
			try:
				os.makedirs(ebuild_dir)
			except os.error:
				pass
			
			metadata = ebuilds[cpv].copy()
			eapi = metadata.pop("EAPI", 0)
			lic = metadata.pop("LICENSE", 0)
			properties = metadata.pop("PROPERTIES", "")
			slot = metadata.pop("SLOT", 0)
			keywords = metadata.pop("KEYWORDS", "x86")
			iuse = metadata.pop("IUSE", "")
			depend = metadata.pop("DEPEND", "")
			rdepend = metadata.pop("RDEPEND", None)
			pdepend = metadata.pop("PDEPEND", None)
			required_use = metadata.pop("REQUIRED_USE", None)

			if metadata:
				raise ValueError("metadata of ebuild '%s' contains unknown keys: %s" % (cpv, metadata.keys()))

			f = open(ebuild_path, "w")
			f.write('EAPI="' + str(eapi) + '"\n')
			f.write('LICENSE="' + str(lic) + '"\n')
			f.write('PROPERTIES="' + str(properties) + '"\n')
			f.write('SLOT="' + str(slot) + '"\n')
			f.write('KEYWORDS="' + str(keywords) + '"\n')
			f.write('IUSE="' + str(iuse) + '"\n')
			f.write('DEPEND="' + str(depend) + '"\n')
			if rdepend is not None:
				f.write('RDEPEND="' + str(rdepend) + '"\n')
			if pdepend is not None:
				f.write('PDEPEND="' + str(pdepend) + '"\n')
			if required_use is not None:
				f.write('REQUIRED_USE="' + str(required_use) + '"\n')
			f.close()

	def _create_ebuild_manifests(self, ebuilds):
		for cpv in ebuilds:
			a = Atom("=" + cpv)
			ebuild_dir = os.path.join(self.portdir, a.cp)
			ebuild_path = os.path.join(ebuild_dir, a.cpv.split("/")[1] + ".ebuild")

			portage.util.noiselimit = -1
			tmpsettings = config(clone=self.settings)
			portdb = self.trees[self.root]["porttree"].dbapi
			portage.doebuild(ebuild_path, "digest", self.root, tmpsettings,
				tree="porttree", mydbapi=portdb)
			portage.util.noiselimit = 0

	def _create_installed(self, installed):
		for cpv in installed:
			a = Atom("=" + cpv)
			vdb_pkg_dir = os.path.join(self.vdbdir, a.cpv)
			try:
				os.makedirs(vdb_pkg_dir)
			except os.error:
				pass

			metadata = installed[cpv].copy()
			eapi = metadata.pop("EAPI", 0)
			lic = metadata.pop("LICENSE", "")
			properties = metadata.pop("PROPERTIES", "")
			slot = metadata.pop("SLOT", 0)
			keywords = metadata.pop("KEYWORDS", "~x86")
			iuse = metadata.pop("IUSE", "")
			use = metadata.pop("USE", "")
			depend = metadata.pop("DEPEND", "")
			rdepend = metadata.pop("RDEPEND", None)
			pdepend = metadata.pop("PDEPEND", None)
			required_use = metadata.pop("REQUIRED_USE", None)

			if metadata:
				raise ValueError("metadata of installed '%s' contains unknown keys: %s" % (cpv, metadata.keys()))

			def write_key(key, value):
				f = open(os.path.join(vdb_pkg_dir, key), "w")
				f.write(str(value) + "\n")
				f.close()
			
			write_key("EAPI", eapi)
			write_key("LICENSE", lic)
			write_key("PROPERTIES", properties)
			write_key("SLOT", slot)
			write_key("KEYWORDS", keywords)
			write_key("IUSE", iuse)
			write_key("USE", use)
			write_key("DEPEND", depend)
			if rdepend is not None:
				write_key("RDEPEND", rdepend)
			if pdepend is not None:
				write_key("PDEPEND", pdepend)
			if required_use is not None:
				write_key("REQUIRED_USE", required_use)

	def _create_profile(self, ebuilds, installed, profile, user_config, sets):
		#Create $PORTDIR/profiles/categories
		categories = set()
		for cpv in chain(ebuilds.keys(), installed.keys()):
			categories.add(catsplit(cpv)[0])
		
		profile_dir = os.path.join(self.portdir, "profiles")
		try:
			os.makedirs(profile_dir)
		except os.error:
			pass
		
		categories_file = os.path.join(profile_dir, "categories")
		
		f = open(categories_file, "w")
		for cat in categories:
			f.write(cat + "\n")
		f.close()
		
		
		#Create $REPO/profiles/license_groups
		license_file = os.path.join(profile_dir, "license_groups")
		f = open(license_file, "w")
		f.write("EULA TEST\n")
		f.close()

		#Create $profile_dir/eclass (we fail to digest the ebuilds if it's not there)
		os.makedirs(os.path.join(self.portdir, "eclass"))

		sub_profile_dir = os.path.join(profile_dir, "default", "linux", "x86", "test_profile")
		os.makedirs(sub_profile_dir)
		
		eapi_file = os.path.join(sub_profile_dir, "eapi")
		f = open(eapi_file, "w")
		f.write("0\n")
		f.close()
		
		make_defaults_file = os.path.join(sub_profile_dir, "make.defaults")
		f = open(make_defaults_file, "w")
		f.write("ARCH=\"x86\"\n")
		f.write("ACCEPT_KEYWORDS=\"x86\"\n")
		f.close()
		
		use_force_file = os.path.join(sub_profile_dir, "use.force")
		f = open(use_force_file, "w")
		f.write("x86\n")
		f.close()

		if profile:
			#This is meant to allow the consumer to set up his own profile,
			#with package.mask and what not.
			raise NotImplementedError()

		#Create profile symlink
		os.makedirs(os.path.join(self.eroot, "etc"))
		os.symlink(sub_profile_dir, os.path.join(self.eroot, "etc", "make.profile"))

		user_config_dir = os.path.join(self.eroot, "etc", "portage")

		try:
			os.makedirs(user_config_dir)
		except os.error:
			pass

		for config_file, lines in user_config.items():
			if config_file not in self.config_files:
				raise ValueError("Unknown config file: '%s'" % config_file)

			file_name = os.path.join(user_config_dir, config_file)
			f = open(file_name, "w")
			for line in lines:
				f.write("%s\n" % line)
			f.close()

		#Create /usr/share/portage/config/sets/portage.conf
		default_sets_conf_dir = os.path.join(self.eroot, "usr/share/portage/config/sets")

		try:
			os.makedirs(default_sets_conf_dir)
		except os.error:
			pass

		provided_sets_portage_conf = \
			os.path.join(PORTAGE_BASE_PATH, "cnf/sets/portage.conf")
		os.symlink(provided_sets_portage_conf, os.path.join(default_sets_conf_dir, "portage.conf"))

		set_config_dir = os.path.join(user_config_dir, "sets")

		try:
			os.makedirs(set_config_dir)
		except os.error:
			pass

		for sets_file, lines in sets.items():
			file_name = os.path.join(set_config_dir, sets_file)
			f = open(file_name, "w")
			for line in lines:
				f.write("%s\n" % line)
			f.close()

	def _create_world(self, world):
		#Create /var/lib/portage/world
		var_lib_portage = os.path.join(self.eroot, "var", "lib", "portage")
		os.makedirs(var_lib_portage)

		world_file = os.path.join(var_lib_portage, "world")

		f = open(world_file, "w")
		for atom in world:
			f.write("%s\n" % atom)
		f.close()

	def _load_config(self):
		env = {
			"ACCEPT_KEYWORDS": "x86",
			"PORTDIR": self.portdir,
			'PORTAGE_TMPDIR'       : os.path.join(self.eroot, 'var/tmp'),
		}

		# Pass along PORTAGE_USERNAME and PORTAGE_GRPNAME since they
		# need to be inherited by ebuild subprocesses.
		if 'PORTAGE_USERNAME' in os.environ:
			env['PORTAGE_USERNAME'] = os.environ['PORTAGE_USERNAME']
		if 'PORTAGE_GRPNAME' in os.environ:
			env['PORTAGE_GRPNAME'] = os.environ['PORTAGE_GRPNAME']

		settings = config(_eprefix=self.eprefix, env=env)
		settings.lock()

		trees = {
			self.root: {
					"vartree": vartree(settings=settings),
					"porttree": portagetree(self.root, settings=settings),
					"bintree": binarytree(self.root,
						os.path.join(self.eroot, "usr/portage/packages"),
						settings=settings)
				}
			}

		for root, root_trees in trees.items():
			settings = root_trees["vartree"].settings
			settings._init_dirs()
			setconfig = load_default_config(settings, root_trees)
			root_trees["root_config"] = RootConfig(settings, root_trees, setconfig)
		
		return settings, trees

	def run(self, atoms, options={}, action=None):
		options = options.copy()
		options["--pretend"] = True
		options["--quiet"] = True
		if self.debug:
			options["--debug"] = True

		if not self.debug:
			portage.util.noiselimit = -2
		params = create_depgraph_params(options, action)
		success, depgraph, favorites = backtrack_depgraph(
			self.settings, self.trees, options, params, action, atoms, None)
		depgraph.display_problems()
		result = ResolverPlaygroundResult(atoms, success, depgraph, favorites)
		portage.util.noiselimit = 0

		return result

	def run_TestCase(self, test_case):
		if not isinstance(test_case, ResolverPlaygroundTestCase):
			raise TypeError("ResolverPlayground needs a ResolverPlaygroundTestCase")
		for atoms in test_case.requests:
			result = self.run(atoms, test_case.options, test_case.action)
			if not test_case.compare_with_result(result):
				return

	def cleanup(self):
		if self.debug:
			print("\nEROOT=%s" % self.eroot)
		else:
			shutil.rmtree(self.eroot)

class ResolverPlaygroundTestCase(object):

	def __init__(self, request, **kwargs):
		self.checks = {
			"success": None,
			"mergelist": None,
			"use_changes": None,
			"unstable_keywords": None,
			"slot_collision_solutions": None,
			"circular_dependency_solutions": None,
			}
		
		self.all_permutations = kwargs.pop("all_permutations", False)
		self.ignore_mergelist_order = kwargs.pop("ignore_mergelist_order", False)

		if self.all_permutations:
			self.requests = list(permutations(request))
		else:
			self.requests = [request]

		self.options = kwargs.pop("options", {})
		self.action = kwargs.pop("action", None)
		self.test_success = True
		self.fail_msg = None
		
		for key, value in kwargs.items():
			if not key in self.checks:
				raise KeyError("Not an avaiable check: '%s'" % key)
			self.checks[key] = value
	
	def compare_with_result(self, result):
		fail_msgs = []
		for key, value in self.checks.items():
			got = getattr(result, key)
			expected = value
			if key == "mergelist" and self.ignore_mergelist_order and got is not None :
				got = set(got)
				expected = set(expected)
			elif key == "unstable_keywords" and expected is not None:
				expected = set(expected)

			if got != expected:
				fail_msgs.append("atoms: (" + ", ".join(result.atoms) + "), key: " + \
					key + ", expected: " + str(expected) + ", got: " + str(got))
		if fail_msgs:
			self.test_success = False
			self.fail_msg = "\n".join(fail_msgs)
			return False
		return True

class ResolverPlaygroundResult(object):
	def __init__(self, atoms, success, mydepgraph, favorites):
		self.atoms = atoms
		self.success = success
		self.depgraph = mydepgraph
		self.favorites = favorites
		self.mergelist = None
		self.use_changes = None
		self.unstable_keywords = None
		self.slot_collision_solutions = None
		self.circular_dependency_solutions = None

		if self.depgraph._dynamic_config._serialized_tasks_cache is not None:
			self.mergelist = []
			for x in self.depgraph._dynamic_config._serialized_tasks_cache:
				if isinstance(x, Blocker):
					self.mergelist.append(x.atom)
				else:
					self.mergelist.append(x.cpv)

		if self.depgraph._dynamic_config._needed_use_config_changes:
			self.use_changes = {}
			for pkg, needed_use_config_changes in \
				self.depgraph._dynamic_config._needed_use_config_changes.items():
				new_use, changes = needed_use_config_changes
				self.use_changes[pkg.cpv] = changes

		if self.depgraph._dynamic_config._needed_unstable_keywords:
			self.unstable_keywords = set()
			for pkg in self.depgraph._dynamic_config._needed_unstable_keywords:
				self.unstable_keywords.add(pkg.cpv)

		if self.depgraph._dynamic_config._slot_conflict_handler is not None:
			self.slot_collision_solutions  = []
			handler = self.depgraph._dynamic_config._slot_conflict_handler

			for solution in handler.solutions:
				s = {}
				for pkg in solution:
					changes = {}
					for flag, state in solution[pkg].items():
						if state == "enabled":
							changes[flag] = True
						else:
							changes[flag] = False
					s[pkg.cpv] = changes
				self.slot_collision_solutions.append(s)

		if self.depgraph._dynamic_config._circular_dependency_handler is not None:
			handler = self.depgraph._dynamic_config._circular_dependency_handler
			sol = handler.solutions
			self.circular_dependency_solutions = dict( zip([x.cpv for x in sol.keys()], sol.values()) )
			
