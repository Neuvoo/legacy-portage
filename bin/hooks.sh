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

# @FUNCTION: hooks_savesetting
# @DESCRIPTION:
# This function saves a variable in the environment into portage's internal
# settings variable, which is not only used by portage but also used as the
# environment for ebuilds. The changes made here are effective until portage
# quits, which means all ebuilds from here on will read them.
# 
# Takes one argument, which is the variable name to save. Arrays are allowed
# but will be read in serialized string form.
# 
# NOTE: to configure only the environment of the currently running ebuild, while
# running inside an ebuild hook, simply set the variable inside the hook.
function hooks_savesetting () {
	local unsecure_varname="$1"
	local varname="$(basename ${unsecure_varname})"
	
	if [[ "${unsecure_varname}" != "${varname}" ]]; then
		eerror "Illegal hooks variable name: ${unsecure_varname}"
		return 1
	fi
	
	# hack: removes the beginning 'declare ... var=[quote]' and ending quote. Suggestions welcome.
	declare -p "${varname}" | sed '1s|^[^=]*=['"'"'"]||; $s|['"'"'"]$||' > "${hooks_tmpdir}/${varname}" || return $?
}

# @FUNCTION: hooks_killportage
# @DESCRIPTION:
# This is a convenience function, which allows a hook to stop portage
# immediately. This will cause portage to exit cleanly, but with an error code.
# 
# Takes one optional argument, which is the signal, passed to kill via the -s
# argument.
function hooks_killportage () {
	local signal="$1"
	
	local args=( )
	if [[ "${signal}" != "" ]]; then
		args+=( -s "${signal}" )
	fi
	args+=( "${PPID}" )
	
	kill "${args[@]}"
}

# Local variables listed here.
# Using the local keyword makes no difference since this script is being sourced
# so we'll have to unset them manually later. Be sure to keep the local_vars
# array up-to-date.
hook_files=( * )
hook_args=( "$@" )
hook_verbosity="0"
local_vars=( "hook_files" "hook_args" "hook_verbosity" )

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
	( eval unset "${local_vars[@]}" '&&' source "${hook}" "${hook_args[@]}" )
	
	exit_code="$?"
	if [[ "${exit_code}" != "0" ]]; then
		eerror "Hook returned with exit code ${exit_code}"
		exit "${exit_code}"
	fi
done

unset "${local_vars[@]}"
