# Copyright 2004-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

__all__ = ['apply_permissions', 'apply_recursive_permissions',
	'apply_secpass_permissions', 'apply_stat_permissions', 'atomic_ofstream',
	'cmp_sort_key', 'ConfigProtect', 'dump_traceback', 'ensure_dirs',
	'find_updated_config_files', 'getconfig', 'getlibpaths', 'grabdict',
	'grabdict_package', 'grabfile', 'grabfile_package', 'grablines',
	'initialize_logger', 'LazyItemsDict', 'map_dictlist_vals',
	'new_protect_filename', 'normalize_path', 'pickle_read', 'stack_dictlist',
	'stack_dicts', 'stack_lists', 'unique_array', 'varexpand', 'write_atomic',
	'writedict', 'writemsg', 'writemsg_level', 'writemsg_stdout']

import codecs
from copy import deepcopy
import errno
import logging
import re
import shlex
import stat
import string
import sys
import traceback

import portage
portage.proxy.lazyimport.lazyimport(globals(),
	'portage.util.listdir:_ignorecvs_dirs'
)
from portage import StringIO
from portage import os
from portage import pickle
from portage import subprocess_getstatusoutput
from portage import _encodings
from portage import _os_merge
from portage import _unicode_encode
from portage import _unicode_decode
from portage.exception import InvalidAtom, PortageException, FileNotFound, \
       OperationNotPermitted, PermissionDenied, ReadOnlyFileSystem
from portage.dep import Atom
from portage.localization import _
from portage.proxy.objectproxy import ObjectProxy
from portage.cache.mappings import UserDict

noiselimit = 0

def initialize_logger(level=logging.WARN):
	"""Sets up basic logging of portage activities
	Args:
		level: the level to emit messages at ('info', 'debug', 'warning' ...)
	Returns:
		None
	"""
	logging.basicConfig(level=logging.WARN, format='[%(levelname)-4s] %(message)s')

def writemsg(mystr,noiselevel=0,fd=None):
	"""Prints out warning and debug messages based on the noiselimit setting"""
	global noiselimit
	if fd is None:
		fd = sys.stderr
	if noiselevel <= noiselimit:
		# avoid potential UnicodeEncodeError
		if isinstance(fd, StringIO):
			mystr = _unicode_decode(mystr,
				encoding=_encodings['content'], errors='replace')
		else:
			mystr = _unicode_encode(mystr,
				encoding=_encodings['stdio'], errors='backslashreplace')
			if sys.hexversion >= 0x3000000 and fd in (sys.stdout, sys.stderr):
				fd = fd.buffer
		fd.write(mystr)
		fd.flush()

def writemsg_stdout(mystr,noiselevel=0):
	"""Prints messages stdout based on the noiselimit setting"""
	writemsg(mystr, noiselevel=noiselevel, fd=sys.stdout)

def writemsg_level(msg, level=0, noiselevel=0):
	"""
	Show a message for the given level as defined by the logging module
	(default is 0). When level >= logging.WARNING then the message is
	sent to stderr, otherwise it is sent to stdout. The noiselevel is
	passed directly to writemsg().

	@type msg: str
	@param msg: a message string, including newline if appropriate
	@type level: int
	@param level: a numeric logging level (see the logging module)
	@type noiselevel: int
	@param noiselevel: passed directly to writemsg
	"""
	if level >= logging.WARNING:
		fd = sys.stderr
	else:
		fd = sys.stdout
	writemsg(msg, noiselevel=noiselevel, fd=fd)

def normalize_path(mypath):
	""" 
	os.path.normpath("//foo") returns "//foo" instead of "/foo"
	We dislike this behavior so we create our own normpath func
	to fix it.
	"""
	if sys.hexversion >= 0x3000000 and isinstance(mypath, bytes):
		path_sep = os.path.sep.encode()
	else:
		path_sep = os.path.sep

	if mypath.startswith(path_sep):
		# posixpath.normpath collapses 3 or more leading slashes to just 1.
		return os.path.normpath(2*path_sep + mypath)
	else:
		return os.path.normpath(mypath)

def grabfile(myfilename, compat_level=0, recursive=0):
	"""This function grabs the lines in a file, normalizes whitespace and returns lines in a list; if a line
	begins with a #, it is ignored, as are empty lines"""

	mylines=grablines(myfilename, recursive)
	newlines=[]
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline = _unicode_decode(' ').join(x.split())
		if not len(myline):
			continue
		if myline[0]=="#":
			# Check if we have a compat-level string. BC-integration data.
			# '##COMPAT==>N<==' 'some string attached to it'
			mylinetest = myline.split("<==",1)
			if len(mylinetest) == 2:
				myline_potential = mylinetest[1]
				mylinetest = mylinetest[0].split("##COMPAT==>")
				if len(mylinetest) == 2:
					if compat_level >= int(mylinetest[1]):
						# It's a compat line, and the key matches.
						newlines.append(myline_potential)
				continue
			else:
				continue
		newlines.append(myline)
	return newlines

def map_dictlist_vals(func,myDict):
	"""Performs a function on each value of each key in a dictlist.
	Returns a new dictlist."""
	new_dl = {}
	for key in myDict:
		new_dl[key] = []
		new_dl[key] = [func(x) for x in myDict[key]]
	return new_dl

def stack_dictlist(original_dicts, incremental=0, incrementals=[], ignore_none=0):
	"""
	Stacks an array of dict-types into one array. Optionally merging or
	overwriting matching key/value pairs for the dict[key]->list.
	Returns a single dict. Higher index in lists is preferenced.
	
	Example usage:
	   >>> from portage.util import stack_dictlist
		>>> print stack_dictlist( [{'a':'b'},{'x':'y'}])
		>>> {'a':'b','x':'y'}
		>>> print stack_dictlist( [{'a':'b'},{'a':'c'}], incremental = True )
		>>> {'a':['b','c'] }
		>>> a = {'KEYWORDS':['x86','alpha']}
		>>> b = {'KEYWORDS':['-x86']}
		>>> print stack_dictlist( [a,b] )
		>>> { 'KEYWORDS':['x86','alpha','-x86']}
		>>> print stack_dictlist( [a,b], incremental=True)
		>>> { 'KEYWORDS':['alpha'] }
		>>> print stack_dictlist( [a,b], incrementals=['KEYWORDS'])
		>>> { 'KEYWORDS':['alpha'] }
	
	@param original_dicts a list of (dictionary objects or None)
	@type list
	@param incremental True or false depending on whether new keys should overwrite
	   keys which already exist.
	@type boolean
	@param incrementals A list of items that should be incremental (-foo removes foo from
	   the returned dict).
	@type list
	@param ignore_none Appears to be ignored, but probably was used long long ago.
	@type boolean
	
	"""
	final_dict = {}
	for mydict in original_dicts:
		if mydict is None:
			continue
		for y in mydict:
			if not y in final_dict:
				final_dict[y] = []
			
			for thing in mydict[y]:
				if thing:
					if incremental or y in incrementals:
						if thing == "-*":
							final_dict[y] = []
							continue
						elif thing[:1] == '-':
							try:
								final_dict[y].remove(thing[1:])
							except ValueError:
								pass
							continue
					if thing not in final_dict[y]:
						final_dict[y].append(thing)
			if y in final_dict and not final_dict[y]:
				del final_dict[y]
	return final_dict

def stack_dicts(dicts, incremental=0, incrementals=[], ignore_none=0):
	"""Stacks an array of dict-types into one array. Optionally merging or
	overwriting matching key/value pairs for the dict[key]->string.
	Returns a single dict."""
	final_dict = {}
	for mydict in dicts:
		if not mydict:
			continue
		for k, v in mydict.items():
			if k in final_dict and (incremental or (k in incrementals)):
				final_dict[k] += " " + v
			else:
				final_dict[k]  = v
	return final_dict

def stack_lists(lists, incremental=1):
	"""Stacks an array of list-types into one array. Optionally removing
	distinct values using '-value' notation. Higher index is preferenced.

	all elements must be hashable."""

	new_list = {}
	for x in lists:
		for y in filter(None, x):
			if incremental:
				if y == "-*":
					new_list.clear()
				elif y[:1] == '-':
					new_list.pop(y[1:], None)
				else:
					new_list[y] = True
			else:
				new_list[y] = True
	return list(new_list)

def grabdict(myfilename, juststrings=0, empty=0, recursive=0, incremental=1):
	"""
	This function grabs the lines in a file, normalizes whitespace and returns lines in a dictionary
	
	@param myfilename: file to process
	@type myfilename: string (path)
	@param juststrings: only return strings
	@type juststrings: Boolean (integer)
	@param empty: Ignore certain lines
	@type empty: Boolean (integer)
	@param recursive: Recursively grab ( support for /etc/portage/package.keywords/* and friends )
	@type recursive: Boolean (integer)
	@param incremental: Append to the return list, don't overwrite
	@type incremental: Boolean (integer)
	@rtype: Dictionary
	@returns:
	1.  Returns the lines in a file in a dictionary, for example:
		'sys-apps/portage x86 amd64 ppc'
		would return
		{ "sys-apps/portage" : [ 'x86', 'amd64', 'ppc' ]
		the line syntax is key : [list of values]
	"""
	newdict={}
	for x in grablines(myfilename, recursive):
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		if x[0] == "#":
			continue
		myline=x.split()
		if len(myline) < 2 and empty == 0:
			continue
		if len(myline) < 1 and empty == 1:
			continue
		if incremental:
			newdict.setdefault(myline[0], []).extend(myline[1:])
		else:
			newdict[myline[0]] = myline[1:]
	if juststrings:
		for k, v in newdict.items():
			newdict[k] = " ".join(v)
	return newdict

def grabdict_package(myfilename, juststrings=0, recursive=0, allow_wildcard=False):
	""" Does the same thing as grabdict except it validates keys
	    with isvalidatom()"""
	pkgs=grabdict(myfilename, juststrings, empty=1, recursive=recursive)
	# We need to call keys() here in order to avoid the possibility of
	# "RuntimeError: dictionary changed size during iteration"
	# when an invalid atom is deleted.
	atoms = {}
	for k, v in pkgs.items():
		try:
			k = Atom(k, allow_wildcard=allow_wildcard)
		except InvalidAtom:
			writemsg(_("--- Invalid atom in %s: %s\n") % (myfilename, k),
				noiselevel=-1)
		else:
			atoms[k] = v
	return atoms

def grabfile_package(myfilename, compatlevel=0, recursive=0, allow_wildcard=False):
	pkgs=grabfile(myfilename, compatlevel, recursive=recursive)
	mybasename = os.path.basename(myfilename)
	atoms = []
	for pkg in pkgs:
		pkg_orig = pkg
		# for packages and package.mask files
		if pkg[:1] == "-":
			pkg = pkg[1:]
		if pkg[:1] == '*' and mybasename == 'packages':
			pkg = pkg[1:]
		try:
			pkg = Atom(pkg, allow_wildcard=allow_wildcard)
		except InvalidAtom:
			writemsg(_("--- Invalid atom in %s: %s\n") % (myfilename, pkg),
				noiselevel=-1)
		else:
			if pkg_orig == str(pkg):
				# normal atom, so return as Atom instance
				atoms.append(pkg)
			else:
				# atom has special prefix, so return as string
				atoms.append(pkg_orig)
	return atoms

def grablines(myfilename,recursive=0):
	mylines=[]
	if recursive and os.path.isdir(myfilename):
		if os.path.basename(myfilename) in _ignorecvs_dirs:
			return mylines
		dirlist = os.listdir(myfilename)
		dirlist.sort()
		for f in dirlist:
			if not f.startswith(".") and not f.endswith("~"):
				mylines.extend(grablines(
					os.path.join(myfilename, f), recursive))
	else:
		try:
			myfile = codecs.open(_unicode_encode(myfilename,
				encoding=_encodings['fs'], errors='strict'),
				mode='r', encoding=_encodings['content'], errors='replace')
			mylines = myfile.readlines()
			myfile.close()
		except IOError as e:
			if e.errno == PermissionDenied.errno:
				raise PermissionDenied(myfilename)
			pass
	return mylines

def writedict(mydict,myfilename,writekey=True):
	"""Writes out a dict to a file; writekey=0 mode doesn't write out
	the key and assumes all values are strings, not lists."""
	myfile = None
	try:
		myfile = atomic_ofstream(myfilename)
		if not writekey:
			for x in mydict.values():
				myfile.write(x+"\n")
		else:
			for x in mydict:
				myfile.write("%s %s\n" % (x, " ".join(mydict[x])))
		myfile.close()
	except IOError:
		if myfile is not None:
			myfile.abort()
		return 0
	return 1

def shlex_split(s):
	"""
	This is equivalent to shlex.split but it temporarily encodes unicode
	strings to bytes since shlex.split() doesn't handle unicode strings.
	"""
	is_unicode = sys.hexversion < 0x3000000 and isinstance(s, unicode)
	if is_unicode:
		s = _unicode_encode(s)
	rval = shlex.split(s)
	if is_unicode:
		rval = [_unicode_decode(x) for x in rval]
	return rval

class _tolerant_shlex(shlex.shlex):
	def sourcehook(self, newfile):
		try:
			return shlex.shlex.sourcehook(self, newfile)
		except EnvironmentError as e:
			writemsg(_("!!! Parse error in '%s': source command failed: %s\n") % \
				(self.infile, str(e)), noiselevel=-1)
			return (newfile, StringIO())

_invalid_var_name_re = re.compile(r'^\d|\W')

def getconfig(mycfg, tolerant=0, allow_sourcing=False, expand=True):
	if isinstance(expand, dict):
		# Some existing variable definitions have been
		# passed in, for use in substitutions.
		expand_map = expand
		expand = True
	else:
		expand_map = {}
	mykeys = {}
	try:
		# Workaround for avoiding a silent error in shlex that
		# is triggered by a source statement at the end of the file without a
		# trailing newline after the source statement
		# NOTE: shex doesn't seem to support unicode objects
		# (produces spurious \0 characters with python-2.6.2)
		if sys.hexversion < 0x3000000:
			content = open(_unicode_encode(mycfg,
				encoding=_encodings['fs'], errors='strict'), 'rb').read()
		else:
			content = open(_unicode_encode(mycfg,
				encoding=_encodings['fs'], errors='strict'), mode='r',
				encoding=_encodings['content'], errors='replace').read()
		if content and content[-1] != '\n':
			content += '\n'
	except IOError as e:
		if e.errno == PermissionDenied.errno:
			raise PermissionDenied(mycfg)
		if e.errno != errno.ENOENT:
			writemsg("open('%s', 'r'): %s\n" % (mycfg, e), noiselevel=-1)
			if e.errno not in (errno.EISDIR,):
				raise
		return None
	try:
		if tolerant:
			shlex_class = _tolerant_shlex
		else:
			shlex_class = shlex.shlex
		# The default shlex.sourcehook() implementation
		# only joins relative paths when the infile
		# attribute is properly set.
		lex = shlex_class(content, infile=mycfg, posix=True)
		lex.wordchars = string.digits + string.ascii_letters + \
			"~!@#$%*_\:;?,./-+{}"
		lex.quotes="\"'"
		if allow_sourcing:
			lex.source="source"
		while 1:
			key=lex.get_token()
			if key == "export":
				key = lex.get_token()
			if key is None:
				#normal end of file
				break;
			equ=lex.get_token()
			if (equ==''):
				#unexpected end of file
				#lex.error_leader(self.filename,lex.lineno)
				if not tolerant:
					writemsg(_("!!! Unexpected end of config file: variable %s\n") % key,
						noiselevel=-1)
					raise Exception(_("ParseError: Unexpected EOF: %s: on/before line %s") % (mycfg, lex.lineno))
				else:
					return mykeys
			elif (equ!='='):
				#invalid token
				#lex.error_leader(self.filename,lex.lineno)
				if not tolerant:
					raise Exception(_("ParseError: Invalid token "
						"'%s' (not '='): %s: line %s") % \
						(equ, mycfg, lex.lineno))
				else:
					return mykeys
			val=lex.get_token()
			if val is None:
				#unexpected end of file
				#lex.error_leader(self.filename,lex.lineno)
				if not tolerant:
					writemsg(_("!!! Unexpected end of config file: variable %s\n") % key,
						noiselevel=-1)
					raise portage.exception.CorruptionError(_("ParseError: Unexpected EOF: %s: line %s") % (mycfg, lex.lineno))
				else:
					return mykeys
			key = _unicode_decode(key)
			val = _unicode_decode(val)

			if _invalid_var_name_re.search(key) is not None:
				if not tolerant:
					raise Exception(_(
						"ParseError: Invalid variable name '%s': line %s") % \
						(key, lex.lineno - 1))
				writemsg(_("!!! Invalid variable name '%s': line %s in %s\n") \
					% (key, lex.lineno - 1, mycfg), noiselevel=-1)
				continue

			if expand:
				mykeys[key] = varexpand(val, expand_map)
				expand_map[key] = mykeys[key]
			else:
				mykeys[key] = val
	except SystemExit as e:
		raise
	except Exception as e:
		raise portage.exception.ParseError(str(e)+" in "+mycfg)
	return mykeys
	
#cache expansions of constant strings
cexpand={}
def varexpand(mystring, mydict=None):
	if mydict is None:
		mydict = {}
	newstring = cexpand.get(" "+mystring, None)
	if newstring is not None:
		return newstring

	"""
	new variable expansion code.  Preserves quotes, handles \n, etc.
	This code is used by the configfile code, as well as others (parser)
	This would be a good bunch of code to port to C.
	"""
	numvars=0
	mystring=" "+mystring
	#in single, double quotes
	insing=0
	indoub=0
	pos=1
	newstring=" "
	while (pos<len(mystring)):
		if (mystring[pos]=="'") and (mystring[pos-1]!="\\"):
			if (indoub):
				newstring=newstring+"'"
			else:
				newstring += "'" # Quote removal is handled by shlex.
				insing=not insing
			pos=pos+1
			continue
		elif (mystring[pos]=='"') and (mystring[pos-1]!="\\"):
			if (insing):
				newstring=newstring+'"'
			else:
				newstring += '"' # Quote removal is handled by shlex.
				indoub=not indoub
			pos=pos+1
			continue
		if (not insing): 
			#expansion time
			if (mystring[pos]=="\n"):
				#convert newlines to spaces
				newstring=newstring+" "
				pos=pos+1
			elif (mystring[pos]=="\\"):
				#backslash expansion time
				if (pos+1>=len(mystring)):
					newstring=newstring+mystring[pos]
					break
				else:
					a=mystring[pos+1]
					pos=pos+2
					if a=='a':
						newstring=newstring+chr(0o07)
					elif a=='b':
						newstring=newstring+chr(0o10)
					elif a=='e':
						newstring=newstring+chr(0o33)
					elif (a=='f') or (a=='n'):
						newstring=newstring+chr(0o12)
					elif a=='r':
						newstring=newstring+chr(0o15)
					elif a=='t':
						newstring=newstring+chr(0o11)
					elif a=='v':
						newstring=newstring+chr(0o13)
					elif a!='\n':
						#remove backslash only, as bash does: this takes care of \\ and \' and \" as well
						newstring=newstring+mystring[pos-1:pos]
						continue
			elif (mystring[pos]=="$") and (mystring[pos-1]!="\\"):
				pos=pos+1
				if mystring[pos]=="{":
					pos=pos+1
					braced=True
				else:
					braced=False
				myvstart=pos
				validchars=string.ascii_letters+string.digits+"_"
				while mystring[pos] in validchars:
					if (pos+1)>=len(mystring):
						if braced:
							cexpand[mystring]=""
							return ""
						else:
							pos=pos+1
							break
					pos=pos+1
				myvarname=mystring[myvstart:pos]
				if braced:
					if mystring[pos]!="}":
						cexpand[mystring]=""
						return ""
					else:
						pos=pos+1
				if len(myvarname)==0:
					cexpand[mystring]=""
					return ""
				numvars=numvars+1
				if myvarname in mydict:
					newstring=newstring+mydict[myvarname] 
			else:
				newstring=newstring+mystring[pos]
				pos=pos+1
		else:
			newstring=newstring+mystring[pos]
			pos=pos+1
	if numvars==0:
		cexpand[mystring]=newstring[1:]
	return newstring[1:]	

# broken and removed, but can still be imported
pickle_write = None

def pickle_read(filename,default=None,debug=0):
	if not os.access(filename, os.R_OK):
		writemsg(_("pickle_read(): File not readable. '")+filename+"'\n",1)
		return default
	data = None
	try:
		myf = open(_unicode_encode(filename,
			encoding=_encodings['fs'], errors='strict'), 'rb')
		mypickle = pickle.Unpickler(myf)
		data = mypickle.load()
		myf.close()
		del mypickle,myf
		writemsg(_("pickle_read(): Loaded pickle. '")+filename+"'\n",1)
	except SystemExit as e:
		raise
	except Exception as e:
		writemsg(_("!!! Failed to load pickle: ")+str(e)+"\n",1)
		data = default
	return data

def dump_traceback(msg, noiselevel=1):
	info = sys.exc_info()
	if not info[2]:
		stack = traceback.extract_stack()[:-1]
		error = None
	else:
		stack = traceback.extract_tb(info[2])
		error = str(info[1])
	writemsg("\n====================================\n", noiselevel=noiselevel)
	writemsg("%s\n\n" % msg, noiselevel=noiselevel)
	for line in traceback.format_list(stack):
		writemsg(line, noiselevel=noiselevel)
	if error:
		writemsg(error+"\n", noiselevel=noiselevel)
	writemsg("====================================\n\n", noiselevel=noiselevel)

class cmp_sort_key(object):
	"""
	In python-3.0 the list.sort() method no longer has a "cmp" keyword
	argument. This class acts as an adapter which converts a cmp function
	into one that's suitable for use as the "key" keyword argument to
	list.sort(), making it easier to port code for python-3.0 compatibility.
	It works by generating key objects which use the given cmp function to
	implement their __lt__ method.
	"""
	__slots__ = ("_cmp_func",)

	def __init__(self, cmp_func):
		"""
		@type cmp_func: callable which takes 2 positional arguments
		@param cmp_func: A cmp function.
		"""
		self._cmp_func = cmp_func

	def __call__(self, lhs):
		return self._cmp_key(self._cmp_func, lhs)

	class _cmp_key(object):
		__slots__ = ("_cmp_func", "_obj")

		def __init__(self, cmp_func, obj):
			self._cmp_func = cmp_func
			self._obj = obj

		def __lt__(self, other):
			if other.__class__ is not self.__class__:
				raise TypeError("Expected type %s, got %s" % \
					(self.__class__, other.__class__))
			return self._cmp_func(self._obj, other._obj) < 0

def unique_array(s):
	"""lifted from python cookbook, credit: Tim Peters
	Return a list of the elements in s in arbitrary order, sans duplicates"""
	n = len(s)
	# assume all elements are hashable, if so, it's linear
	try:
		return list(set(s))
	except TypeError:
		pass

	# so much for linear.  abuse sort.
	try:
		t = list(s)
		t.sort()
	except TypeError:
		pass
	else:
		assert n > 0
		last = t[0]
		lasti = i = 1
		while i < n:
			if t[i] != last:
				t[lasti] = last = t[i]
				lasti += 1
			i += 1
		return t[:lasti]

	# blah.	 back to original portage.unique_array
	u = []
	for x in s:
		if x not in u:
			u.append(x)
	return u

def apply_permissions(filename, uid=-1, gid=-1, mode=-1, mask=-1,
	stat_cached=None, follow_links=True):
	"""Apply user, group, and mode bits to a file if the existing bits do not
	already match.  The default behavior is to force an exact match of mode
	bits.  When mask=0 is specified, mode bits on the target file are allowed
	to be a superset of the mode argument (via logical OR).  When mask>0, the
	mode bits that the target file is allowed to have are restricted via
	logical XOR.
	Returns True if the permissions were modified and False otherwise."""

	modified = False

	if stat_cached is None:
		try:
			if follow_links:
				stat_cached = os.stat(filename)
			else:
				stat_cached = os.lstat(filename)
		except OSError as oe:
			func_call = "stat('%s')" % filename
			if oe.errno == errno.EPERM:
				raise OperationNotPermitted(func_call)
			elif oe.errno == errno.EACCES:
				raise PermissionDenied(func_call)
			elif oe.errno == errno.ENOENT:
				raise FileNotFound(filename)
			else:
				raise

	if	(uid != -1 and uid != stat_cached.st_uid) or \
		(gid != -1 and gid != stat_cached.st_gid):
		try:
			if follow_links:
				os.chown(filename, uid, gid)
			else:
				portage.data.lchown(filename, uid, gid)
			modified = True
		except OSError as oe:
			func_call = "chown('%s', %i, %i)" % (filename, uid, gid)
			if oe.errno == errno.EPERM:
				raise OperationNotPermitted(func_call)
			elif oe.errno == errno.EACCES:
				raise PermissionDenied(func_call)
			elif oe.errno == errno.EROFS:
				raise ReadOnlyFileSystem(func_call)
			elif oe.errno == errno.ENOENT:
				raise FileNotFound(filename)
			else:
				raise

	new_mode = -1
	st_mode = stat_cached.st_mode & 0o7777 # protect from unwanted bits
	if mask >= 0:
		if mode == -1:
			mode = 0 # Don't add any mode bits when mode is unspecified.
		else:
			mode = mode & 0o7777
		if	(mode & st_mode != mode) or \
			((mask ^ st_mode) & st_mode != st_mode):
			new_mode = mode | st_mode
			new_mode = (mask ^ new_mode) & new_mode
	elif mode != -1:
		mode = mode & 0o7777 # protect from unwanted bits
		if mode != st_mode:
			new_mode = mode

	# The chown system call may clear S_ISUID and S_ISGID
	# bits, so those bits are restored if necessary.
	if modified and new_mode == -1 and \
		(st_mode & stat.S_ISUID or st_mode & stat.S_ISGID):
		if mode == -1:
			new_mode = st_mode
		else:
			mode = mode & 0o7777
			if mask >= 0:
				new_mode = mode | st_mode
				new_mode = (mask ^ new_mode) & new_mode
			else:
				new_mode = mode
			if not (new_mode & stat.S_ISUID or new_mode & stat.S_ISGID):
				new_mode = -1

	if not follow_links and stat.S_ISLNK(stat_cached.st_mode):
		# Mode doesn't matter for symlinks.
		new_mode = -1

	if new_mode != -1:
		try:
			os.chmod(filename, new_mode)
			modified = True
		except OSError as oe:
			func_call = "chmod('%s', %s)" % (filename, oct(new_mode))
			if oe.errno == errno.EPERM:
				raise OperationNotPermitted(func_call)
			elif oe.errno == errno.EACCES:
				raise PermissionDenied(func_call)
			elif oe.errno == errno.EROFS:
				raise ReadOnlyFileSystem(func_call)
			elif oe.errno == errno.ENOENT:
				raise FileNotFound(filename)
			raise
	return modified

def apply_stat_permissions(filename, newstat, **kwargs):
	"""A wrapper around apply_secpass_permissions that gets
	uid, gid, and mode from a stat object"""
	return apply_secpass_permissions(filename, uid=newstat.st_uid, gid=newstat.st_gid,
	mode=newstat.st_mode, **kwargs)

def apply_recursive_permissions(top, uid=-1, gid=-1,
	dirmode=-1, dirmask=-1, filemode=-1, filemask=-1, onerror=None):
	"""A wrapper around apply_secpass_permissions that applies permissions
	recursively.  If optional argument onerror is specified, it should be a
	function; it will be called with one argument, a PortageException instance.
	Returns True if all permissions are applied and False if some are left
	unapplied."""

	if onerror is None:
		# Default behavior is to dump errors to stderr so they won't
		# go unnoticed.  Callers can pass in a quiet instance.
		def onerror(e):
			if isinstance(e, OperationNotPermitted):
				writemsg(_("Operation Not Permitted: %s\n") % str(e),
					noiselevel=-1)
			elif isinstance(e, FileNotFound):
				writemsg(_("File Not Found: '%s'\n") % str(e), noiselevel=-1)
			else:
				raise

	all_applied = True
	for dirpath, dirnames, filenames in os.walk(top):
		try:
			applied = apply_secpass_permissions(dirpath,
				uid=uid, gid=gid, mode=dirmode, mask=dirmask)
			if not applied:
				all_applied = False
		except PortageException as e:
			all_applied = False
			onerror(e)

		for name in filenames:
			try:
				applied = apply_secpass_permissions(os.path.join(dirpath, name),
					uid=uid, gid=gid, mode=filemode, mask=filemask)
				if not applied:
					all_applied = False
			except PortageException as e:
				# Ignore InvalidLocation exceptions such as FileNotFound
				# and DirectoryNotFound since sometimes things disappear,
				# like when adjusting permissions on DISTCC_DIR.
				if not isinstance(e, portage.exception.InvalidLocation):
					all_applied = False
					onerror(e)
	return all_applied

def apply_secpass_permissions(filename, uid=-1, gid=-1, mode=-1, mask=-1,
	stat_cached=None, follow_links=True):
	"""A wrapper around apply_permissions that uses secpass and simple
	logic to apply as much of the permissions as possible without
	generating an obviously avoidable permission exception. Despite
	attempts to avoid an exception, it's possible that one will be raised
	anyway, so be prepared.
	Returns True if all permissions are applied and False if some are left
	unapplied."""

	if stat_cached is None:
		try:
			if follow_links:
				stat_cached = os.stat(filename)
			else:
				stat_cached = os.lstat(filename)
		except OSError as oe:
			func_call = "stat('%s')" % filename
			if oe.errno == errno.EPERM:
				raise OperationNotPermitted(func_call)
			elif oe.errno == errno.EACCES:
				raise PermissionDenied(func_call)
			elif oe.errno == errno.ENOENT:
				raise FileNotFound(filename)
			else:
				raise

	all_applied = True

	if portage.data.secpass < 2:

		if uid != -1 and \
		uid != stat_cached.st_uid:
			all_applied = False
			uid = -1

		if gid != -1 and \
		gid != stat_cached.st_gid and \
		gid not in os.getgroups():
			all_applied = False
			gid = -1

	apply_permissions(filename, uid=uid, gid=gid, mode=mode, mask=mask,
		stat_cached=stat_cached, follow_links=follow_links)
	return all_applied

class atomic_ofstream(ObjectProxy):
	"""Write a file atomically via os.rename().  Atomic replacement prevents
	interprocess interference and prevents corruption of the target
	file when the write is interrupted (for example, when an 'out of space'
	error occurs)."""

	def __init__(self, filename, mode='w', follow_links=True, **kargs):
		"""Opens a temporary filename.pid in the same directory as filename."""
		ObjectProxy.__init__(self)
		object.__setattr__(self, '_aborted', False)
		if 'b' in mode:
			open_func = open
		else:
			open_func = codecs.open
			kargs.setdefault('encoding', _encodings['content'])
			kargs.setdefault('errors', 'backslashreplace')

		if follow_links:
			canonical_path = os.path.realpath(filename)
			object.__setattr__(self, '_real_name', canonical_path)
			tmp_name = "%s.%i" % (canonical_path, os.getpid())
			try:
				object.__setattr__(self, '_file',
					open_func(_unicode_encode(tmp_name,
						encoding=_encodings['fs'], errors='strict'),
						mode=mode, **kargs))
				return
			except IOError as e:
				if canonical_path == filename:
					raise
				writemsg(_("!!! Failed to open file: '%s'\n") % tmp_name,
					noiselevel=-1)
				writemsg("!!! %s\n" % str(e), noiselevel=-1)

		object.__setattr__(self, '_real_name', filename)
		tmp_name = "%s.%i" % (filename, os.getpid())
		object.__setattr__(self, '_file',
			open_func(_unicode_encode(tmp_name,
				encoding=_encodings['fs'], errors='strict'),
				mode=mode, **kargs))

	def _get_target(self):
		return object.__getattribute__(self, '_file')

	def __getattribute__(self, attr):
		if attr in ('close', 'abort', '__del__'):
			return object.__getattribute__(self, attr)
		return getattr(object.__getattribute__(self, '_file'), attr)

	def close(self):
		"""Closes the temporary file, copies permissions (if possible),
		and performs the atomic replacement via os.rename().  If the abort()
		method has been called, then the temp file is closed and removed."""
		f = object.__getattribute__(self, '_file')
		real_name = object.__getattribute__(self, '_real_name')
		if not f.closed:
			try:
				f.close()
				if not object.__getattribute__(self, '_aborted'):
					try:
						apply_stat_permissions(f.name, os.stat(real_name))
					except OperationNotPermitted:
						pass
					except FileNotFound:
						pass
					except OSError as oe: # from the above os.stat call
						if oe.errno in (errno.ENOENT, errno.EPERM):
							pass
						else:
							raise
					os.rename(f.name, real_name)
			finally:
				# Make sure we cleanup the temp file
				# even if an exception is raised.
				try:
					os.unlink(f.name)
				except OSError as oe:
					pass

	def abort(self):
		"""If an error occurs while writing the file, the user should
		call this method in order to leave the target file unchanged.
		This will call close() automatically."""
		if not object.__getattribute__(self, '_aborted'):
			object.__setattr__(self, '_aborted', True)
			self.close()

	def __del__(self):
		"""If the user does not explicitely call close(), it is
		assumed that an error has occurred, so we abort()."""
		try:
			f = object.__getattribute__(self, '_file')
		except AttributeError:
			pass
		else:
			if not f.closed:
				self.abort()
		# ensure destructor from the base class is called
		base_destructor = getattr(ObjectProxy, '__del__', None)
		if base_destructor is not None:
			base_destructor(self)

def write_atomic(file_path, content, **kwargs):
	f = None
	try:
		f = atomic_ofstream(file_path, **kwargs)
		f.write(content)
		f.close()
	except (IOError, OSError) as e:
		if f:
			f.abort()
		func_call = "write_atomic('%s')" % file_path
		if e.errno == errno.EPERM:
			raise OperationNotPermitted(func_call)
		elif e.errno == errno.EACCES:
			raise PermissionDenied(func_call)
		elif e.errno == errno.EROFS:
			raise ReadOnlyFileSystem(func_call)
		elif e.errno == errno.ENOENT:
			raise FileNotFound(file_path)
		else:
			raise

def ensure_dirs(dir_path, *args, **kwargs):
	"""Create a directory and call apply_permissions.
	Returns True if a directory is created or the permissions needed to be
	modified, and False otherwise."""

	created_dir = False

	try:
		os.makedirs(dir_path)
		created_dir = True
	except OSError as oe:
		func_call = "makedirs('%s')" % dir_path
		if oe.errno in (errno.EEXIST, errno.EISDIR):
			pass
		else:
			if os.path.isdir(dir_path):
				# NOTE: DragonFly raises EPERM for makedir('/')
				# and that is supposed to be ignored here.
				pass
			elif oe.errno == errno.EPERM:
				raise OperationNotPermitted(func_call)
			elif oe.errno == errno.EACCES:
				raise PermissionDenied(func_call)
			elif oe.errno == errno.EROFS:
				raise ReadOnlyFileSystem(func_call)
			else:
				raise
	perms_modified = apply_permissions(dir_path, *args, **kwargs)
	return created_dir or perms_modified

class LazyItemsDict(UserDict):
	"""A mapping object that behaves like a standard dict except that it allows
	for lazy initialization of values via callable objects.  Lazy items can be
	overwritten and deleted just as normal items."""

	__slots__ = ('lazy_items',)

	def __init__(self, *args, **kwargs):

		self.lazy_items = {}
		UserDict.__init__(self, *args, **kwargs)

	def addLazyItem(self, item_key, value_callable, *pargs, **kwargs):
		"""Add a lazy item for the given key.  When the item is requested,
		value_callable will be called with *pargs and **kwargs arguments."""
		self.lazy_items[item_key] = \
			self._LazyItem(value_callable, pargs, kwargs, False)
		# make it show up in self.keys(), etc...
		UserDict.__setitem__(self, item_key, None)

	def addLazySingleton(self, item_key, value_callable, *pargs, **kwargs):
		"""This is like addLazyItem except value_callable will only be called
		a maximum of 1 time and the result will be cached for future requests."""
		self.lazy_items[item_key] = \
			self._LazyItem(value_callable, pargs, kwargs, True)
		# make it show up in self.keys(), etc...
		UserDict.__setitem__(self, item_key, None)

	def update(self, *args, **kwargs):
		if len(args) > 1:
			raise TypeError(
				"expected at most 1 positional argument, got " + \
				repr(len(args)))
		if args:
			map_obj = args[0]
		else:
			map_obj = None
		if map_obj is None:
			pass
		elif isinstance(map_obj, LazyItemsDict):
			for k in map_obj:
				if k in map_obj.lazy_items:
					UserDict.__setitem__(self, k, None)
				else:
					UserDict.__setitem__(self, k, map_obj[k])
			self.lazy_items.update(map_obj.lazy_items)
		else:
			UserDict.update(self, map_obj)
		if kwargs:
			UserDict.update(self, kwargs)

	def __getitem__(self, item_key):
		if item_key in self.lazy_items:
			lazy_item = self.lazy_items[item_key]
			pargs = lazy_item.pargs
			if pargs is None:
				pargs = ()
			kwargs = lazy_item.kwargs
			if kwargs is None:
				kwargs = {}
			result = lazy_item.func(*pargs, **kwargs)
			if lazy_item.singleton:
				self[item_key] = result
			return result

		else:
			return UserDict.__getitem__(self, item_key)

	def __setitem__(self, item_key, value):
		if item_key in self.lazy_items:
			del self.lazy_items[item_key]
		UserDict.__setitem__(self, item_key, value)

	def __delitem__(self, item_key):
		if item_key in self.lazy_items:
			del self.lazy_items[item_key]
		UserDict.__delitem__(self, item_key)

	def clear(self):
		self.lazy_items.clear()
		UserDict.clear(self)

	def copy(self):
		return self.__copy__()

	def __copy__(self):
		return self.__class__(self)

	def __deepcopy__(self, memo=None):
		"""
		WARNING: If any of the lazy items contains a bound method then it's
		typical for deepcopy() to raise an exception like this:

			File "/usr/lib/python2.5/copy.py", line 189, in deepcopy
				y = _reconstruct(x, rv, 1, memo)
			File "/usr/lib/python2.5/copy.py", line 322, in _reconstruct
				y = callable(*args)
			File "/usr/lib/python2.5/copy_reg.py", line 92, in __newobj__
				return cls.__new__(cls, *args)
			TypeError: instancemethod expected at least 2 arguments, got 0

		If deepcopy() needs to work, this problem can be avoided by
		implementing lazy items with normal (non-bound) functions.

		If deepcopy() raises a TypeError for a lazy item that has been added
		via a call to addLazySingleton(), the singleton will be automatically
		evaluated and deepcopy() will instead be called on the result.
		"""
		if memo is None:
			memo = {}
		result = self.__class__()
		memo[id(self)] = result
		for k in self:
			k_copy = deepcopy(k, memo)
			if k in self.lazy_items:
				lazy_item = self.lazy_items[k]
				try:
					result.lazy_items[k_copy] = deepcopy(lazy_item, memo)
				except TypeError:
					if not lazy_item.singleton:
						raise
					UserDict.__setitem__(result,
						k_copy, deepcopy(self[k], memo))
				else:
					UserDict.__setitem__(result, k_copy, None)
			else:
				UserDict.__setitem__(result, k_copy, deepcopy(self[k], memo))
		return result

	class _LazyItem(object):

		__slots__ = ('func', 'pargs', 'kwargs', 'singleton')

		def __init__(self, func, pargs, kwargs, singleton):

			if not pargs:
				pargs = None
			if not kwargs:
				kwargs = None

			self.func = func
			self.pargs = pargs
			self.kwargs = kwargs
			self.singleton = singleton

		def __copy__(self):
			return self.__class__(self.func, self.pargs,
				self.kwargs, self.singleton)

		def __deepcopy__(self, memo=None):
			"""
			Override this since the default implementation can fail silently,
			leaving some attributes unset.
			"""
			if memo is None:
				memo = {}
			result = self.__copy__()
			memo[id(self)] = result
			result.func = deepcopy(self.func, memo)
			result.pargs = deepcopy(self.pargs, memo)
			result.kwargs = deepcopy(self.kwargs, memo)
			result.singleton = deepcopy(self.singleton, memo)
			return result

class ConfigProtect(object):
	def __init__(self, myroot, protect_list, mask_list):
		self.myroot = myroot
		self.protect_list = protect_list
		self.mask_list = mask_list
		self.updateprotect()

	def updateprotect(self):
		"""Update internal state for isprotected() calls.  Nonexistent paths
		are ignored."""

		os = _os_merge

		self.protect = []
		self._dirs = set()
		for x in self.protect_list:
			ppath = normalize_path(
				os.path.join(self.myroot, x.lstrip(os.path.sep)))
			try:
				if stat.S_ISDIR(os.stat(ppath).st_mode):
					self._dirs.add(ppath)
				self.protect.append(ppath)
			except OSError:
				# If it doesn't exist, there's no need to protect it.
				pass

		self.protectmask = []
		for x in self.mask_list:
			ppath = normalize_path(
				os.path.join(self.myroot, x.lstrip(os.path.sep)))
			try:
				"""Use lstat so that anything, even a broken symlink can be
				protected."""
				if stat.S_ISDIR(os.lstat(ppath).st_mode):
					self._dirs.add(ppath)
				self.protectmask.append(ppath)
				"""Now use stat in case this is a symlink to a directory."""
				if stat.S_ISDIR(os.stat(ppath).st_mode):
					self._dirs.add(ppath)
			except OSError:
				# If it doesn't exist, there's no need to mask it.
				pass

	def isprotected(self, obj):
		"""Returns True if obj is protected, False otherwise.  The caller must
		ensure that obj is normalized with a single leading slash.  A trailing
		slash is optional for directories."""
		masked = 0
		protected = 0
		sep = os.path.sep
		for ppath in self.protect:
			if len(ppath) > masked and obj.startswith(ppath):
				if ppath in self._dirs:
					if obj != ppath and not obj.startswith(ppath + sep):
						# /etc/foo does not match /etc/foobaz
						continue
				elif obj != ppath:
					# force exact match when CONFIG_PROTECT lists a
					# non-directory
					continue
				protected = len(ppath)
				#config file management
				for pmpath in self.protectmask:
					if len(pmpath) >= protected and obj.startswith(pmpath):
						if pmpath in self._dirs:
							if obj != pmpath and \
								not obj.startswith(pmpath + sep):
								# /etc/foo does not match /etc/foobaz
								continue
						elif obj != pmpath:
							# force exact match when CONFIG_PROTECT_MASK lists
							# a non-directory
							continue
						#skip, it's in the mask
						masked = len(pmpath)
		return protected > masked

def new_protect_filename(mydest, newmd5=None):
	"""Resolves a config-protect filename for merging, optionally
	using the last filename if the md5 matches.
	(dest,md5) ==> 'string'            --- path_to_target_filename
	(dest)     ==> ('next', 'highest') --- next_target and most-recent_target
	"""

	# config protection filename format:
	# ._cfg0000_foo
	# 0123456789012

	os = _os_merge

	prot_num = -1
	last_pfile = ""

	if not os.path.exists(mydest):
		return mydest

	real_filename = os.path.basename(mydest)
	real_dirname  = os.path.dirname(mydest)
	for pfile in os.listdir(real_dirname):
		if pfile[0:5] != "._cfg":
			continue
		if pfile[10:] != real_filename:
			continue
		try:
			new_prot_num = int(pfile[5:9])
			if new_prot_num > prot_num:
				prot_num = new_prot_num
				last_pfile = pfile
		except ValueError:
			continue
	prot_num = prot_num + 1

	new_pfile = normalize_path(os.path.join(real_dirname,
		"._cfg" + str(prot_num).zfill(4) + "_" + real_filename))
	old_pfile = normalize_path(os.path.join(real_dirname, last_pfile))
	if last_pfile and newmd5:
		try:
			last_pfile_md5 = portage.checksum._perform_md5_merge(old_pfile)
		except FileNotFound:
			# The file suddenly disappeared or it's a broken symlink.
			pass
		else:
			if last_pfile_md5 == newmd5:
				return old_pfile
	return new_pfile

def find_updated_config_files(target_root, config_protect):
	"""
	Return a tuple of configuration files that needs to be updated.
	The tuple contains lists organized like this:
	[ protected_dir, file_list ]
	If the protected config isn't a protected_dir but a procted_file, list is:
	[ protected_file, None ]
	If no configuration files needs to be updated, None is returned
	"""

	os = _os_merge

	if config_protect:
		# directories with some protect files in them
		for x in config_protect:
			files = []

			x = os.path.join(target_root, x.lstrip(os.path.sep))
			if not os.access(x, os.W_OK):
				continue
			try:
				mymode = os.lstat(x).st_mode
			except OSError:
				continue

			if stat.S_ISLNK(mymode):
				# We want to treat it like a directory if it
				# is a symlink to an existing directory.
				try:
					real_mode = os.stat(x).st_mode
					if stat.S_ISDIR(real_mode):
						mymode = real_mode
				except OSError:
					pass

			if stat.S_ISDIR(mymode):
				mycommand = \
					"find '%s' -name '.*' -type d -prune -o -name '._cfg????_*'" % x
			else:
				mycommand = "find '%s' -maxdepth 1 -name '._cfg????_%s'" % \
						os.path.split(x.rstrip(os.path.sep))
			mycommand += " ! -name '.*~' ! -iname '.*.bak' -print0"
			a = subprocess_getstatusoutput(mycommand)

			if a[0] == 0:
				files = a[1].split('\0')
				# split always produces an empty string as the last element
				if files and not files[-1]:
					del files[-1]
				if files:
					if stat.S_ISDIR(mymode):
						yield (x, files)
					else:
						yield (x, None)

def getlibpaths(root):
	""" Return a list of paths that are used for library lookups """

	# the following is based on the information from ld.so(8)
	rval = os.environ.get("LD_LIBRARY_PATH", "").split(":")
	rval.extend(grabfile(os.path.join(root, "etc", "ld.so.conf")))
	rval.append("/usr/lib")
	rval.append("/lib")

	return [normalize_path(x) for x in rval if x]
