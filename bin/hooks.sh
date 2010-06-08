#!/bin/bash
# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

# @MAINTAINER:
# jacobgodserv@gmail.com
# @BLURB: Executes hooks in the current directory.
# @DESCRIPTION:
# Part of the portage hooks system, this script is responsible for executing
# hooks within a prepared environment, as well as acting as an API interface
# between hooks and portage.

# Only run hooks if it's requested in $FEATURES
if ! (source "${PORTAGE_BIN_PATH}/isolated-functions.sh" && hasq hooks $FEATURES) ; then
	return
fi

# TODO: unit testing does not cover this portion of hooks.sh
# This code is put here so it's easier to do one-liners elsewhere.
# This section is meant to be run by ebuild.sh
if [[ "$1" == "--do-pre-ebuild" || "$1" == "--do-post-ebuild" ]]; then
	if [[ "${EBUILD_PHASE}" == "" ]]; then
		# an in-between-phases moment; useless to hooks
		return
	fi
	

	oldwd="$(pwd)"
	if [[ "$1" == "--do-pre-ebuild" ]]; then
		hooks_dir="${PORTAGE_CONFIGROOT}/${HOOKS_PATH}/pre-ebuild.d"
	else
		hooks_dir="${PORTAGE_CONFIGROOT}/${HOOKS_PATH}/post-ebuild.d"
	fi
	
	[ -d "${hooks_dir}" ] && cd "${hooks_dir}"
	exit_code="$?"
	if [[ "${exit_code}" != "0" ]]; then
		# mimicks behavior in hooks.py
		# TODO: --verbose detection?
		:
		#debug-print "This hook path could not be found; ignored: ${hooks_dir}"
	else
		# Create the temporary directory if needed
		if [ ! -d "${HOOKS_TMPDIR}" ]; then
			mkdir "${HOOKS_TMPDIR}" || die "Could not create temporary hooks output directory: ${HOOKS_TMPDIR}"
		fi
		
		# Execute the hooks
		source "${HOOKS_SH_BINARY}" --action "${EBUILD_PHASE}" --target "${EBUILD}"
		exit_code="$?"
		if [[ "${exit_code}" != "0" ]]; then
			# mimicks behavior in hooks.py
			die "Hook directory ${HOOKS_PATH}/pre-ebuild.d failed with exit code ${exit_code}"
		fi
	fi
	cd "${oldwd}" || die "Could not return to the old ebuild directory after pre-ebuild hooks: ${oldwd}"
	
	return
fi

# Local variables listed here.
# Using the local keyword makes no difference since this script is being sourced
# so we'll have to unset them manually later. Be sure to keep the local_vars
# array up-to-date.
hook_files=( * )
hook_args=( "$@" )
hook_verbosity="0"
HOOKS_TMPDIR_settings="${HOOKS_TMPDIR}/settings/"
HOOKS_TMPDIR_envonly="${HOOKS_TMPDIR}/envonly/"

hook_local_vars=( "hook_files" "hook_args" "hook_verbosity" ) # variables unset for hooks
quit_local_vars=( "HOOKS_TMPDIR_settings" "HOOKS_TMPDIR_envonly" "${hook_local_vars[@]}" ) # variables unset at quit

# Create the directories we'll be using, if they don't already exist.
# Settings directory can exist, since it's global anyway
if [ ! -d "${HOOKS_TMPDIR_settings}" ]; then
	mkdir "${HOOKS_TMPDIR_settings}" || exit $?
fi
# Envonly directory cannot exist, since these vars are local only
[ -d "${HOOKS_TMPDIR_envonly}" ] && rm -rf "${HOOKS_TMPDIR_envonly}"
mkdir "${HOOKS_TMPDIR_envonly}" || exit $?

# @FUNCTION: hooks_savesetting
# @DESCRIPTION:
# This function saves a variable in the environment into portage's internal
# settings variable, which is not only used by portage but also used as the
# environment for ebuilds. The changes made here are effective until portage
# quits, which means all ebuilds from here on will read them.
#
# Be careful: portage resets the internal settings variable at each ebuild phase
# and only allows whitelisted variables to persist beyond ebuild phases. Do not
# use this to store hook-specific settings!
# 
# Takes one argument, which is the variable name to save. Arrays are allowed but
# discouraged, since portage will read them as serialized strings only.
function hooks_savesetting () {
	hooks_savevarto "$1" "${HOOKS_TMPDIR_settings}" || return $?
}

# @FUNCTION: hooks_saveenvonly
# @DESCRIPTION:
# Like hooks_savesetting, except that the variable will only be saved so that
# future hooks and, if it is an ebuild hook, the current ebuild phase will see
# it. In other words, the big difference is this change isn't saved in portage's
# internal settings variable while portage is running.
# 
# Takes one argument, which is the variable name to save. Arrays are allowed.
function hooks_saveenvonly () {
	hooks_savevarto "$1" "${HOOKS_TMPDIR_envonly}" || return $?
}

# @FUNCTION: hooks_savevarto
# @DESCRIPTION:
# Hook developers are highly discouraged from calling directly.
#
# Used by hook APIs to serialize a variable to a file inside the specified
# directory.
# 
# Takes two arguments:
# * First is the variable name to save. Arrays are allowed, but if portage is to
#   read this variable back, it will be read as a string.
# * Second is the directory, which must exist. The variable name, after
#   processed by basename, will be used as the file name.
function hooks_savevarto () {
	local unsecure_varname="$1"
	local directory="$2"
	local varname="$(basename ${unsecure_varname})"
	
	if [[ "${unsecure_varname}" != "${varname}" ]]; then
		eerror "Illegal hooks variable name: ${unsecure_varname}"
		return 1
	fi
	
	if [ ! -d "${directory}" ]; then
		eerror "${directory} is not a directory"
		return 1
	fi
	
	# removes the beginning junk we don't want, up to the equals sign
	declare -p "${varname}" | sed '1s|^[^=]*=||' > "${directory}/${varname}" || return $?
}

# @FUNCTION: hooks_killportage
# @DESCRIPTION:
# This is a convenience function, which allows a hook to stop portage
# immediately. This will cause portage to exit without whining too much.
# Portage will still exit with an error code, breaking wrapper scripts like
# eix-sync.
# 
# Takes one optional argument, which is the kill signal, passed to kill via the
# -s argument. Otherwise, uses kill's default signal.

# TODO: unable to test with unit tests, since it forces even the testing module
# to quit
function hooks_killportage () {
	local signal="$1"
	
	local args=( )
	if [[ "${signal}" != "" ]]; then
		args+=( -s "${signal}" )
	fi
	args+=( "${PPID}" )
	
	kill "${args[@]}"
}

for (( i = 0 ; i < ${#hook_args[@]} ; i++ )); do
	if [[ "${hook_args[$i]}" == "--verbose" ]]; then
		hook_verbosity="1"
	fi
done

for (( i = 0 ; i < ${#hook_files[@]} ; i++ )); do
	hook="${hook_files[$i]}"
	if [[ ! -f "${hook}" ]]; then
		[ "${hook_verbosity}" -gt 0 ] && ewarn "Only files are recognized in a hook directory: ${hook}"
		continue
	fi
	
	[ "${hook_verbosity}" -gt 0 ] && einfo "Executing hook ${hook}..."
	# We use eval so the hook_args gets expanded before it is unset
	( eval unset "${hook_local_vars[@]}" '&&' source "${hook}" "${hook_args[@]}" )
	
	exit_code="$?"
	if [[ "${exit_code}" != "0" ]]; then
		eerror "Hook $(pwd)/${hook} returned with exit code ${exit_code}"
		exit "${exit_code}"
	fi
	
	# We need to re-export variables that hooks saved. The goal is to let the
	# specifically-saved variables escape the hook "( ... )" subshell and carry
	# over into the next hook or an ebuild env.
	var_files=( "${HOOKS_TMPDIR_envonly}"/* "${HOOKS_TMPDIR_settings}"/* )
	for (( varI = 0 ; varI < ${#var_files[@]} ; varI++ )); do
		varname="$(basename ${var_files[$varI]})"
		# if there are no files, the variable points to a non-existant file, which we want to catch here
		if [ ! -f "${var_files[$varI]}" ]; then
			continue;
		fi
		# if the variable is not read-only
		if $(unset "${varname}" 2> /dev/null) ; then
			eval declare -x "$(basename ${var_files[$varI]})"="$(cat ${var_files[$varI]})" || exit $?
		else
			ewarn "A hook tried to modify a read-only variable: ${varname}"
		fi
	done
done

unset "${quit_local_vars[@]}"
