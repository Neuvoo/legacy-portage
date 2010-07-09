#!/bin/bash
# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

# @MAINTAINER:
# jacobgodserv@gmail.com
# @BLURB: Executes hooks in the current directory.
# @DESCRIPTION:
# Part of the portage hooks system, this script is responsible for executing
# hooks within a prepared environment

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

hook_local_vars=( "hook_files" "hook_args" "hook_verbosity" ) # variables unset for hooks

for (( i = 0 ; i < ${#hook_args[@]} ; i++ )); do
	if [[ "${hook_args[$i]}" == "--verbose" ]]; then
		hook_verbosity="1"
	fi
done

for (( i = 0 ; i < ${#hook_files[@]} ; i++ )); do
	hook="${hook_files[$i]}"
	if [[ ! -e "${hook}" ]]; then
		continue
	elif [[ ! -f "${hook}" ]]; then
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
done

unset "${hook_local_vars[@]}"
