#!/bin/bash
# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

function hooksave () {
	local unsecure_varname="$1"
	local varname="$(basename ${unsecure_varname})"
	
	if [[ "${unsecure_varname}" != "${varname}" ]]; then
		eerror "Illegal hooks variable name: ${unsecure_varname}"
		return 1
	fi
	
	# hack: removes the beginning 'declare ... var=[quote]' and ending quote. Suggestions welcome.
	declare -p "${varname}" | sed '1s|^[^=]*=['"'"'"]||; $s|['"'"'"]$||' > "${hooks_tmpdir}/${varname}" || return $?
}

# local variables listed here
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
