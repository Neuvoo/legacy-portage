#!/bin/bash

RELEASE_BUILDDIR=${RELEASE_BUILDDIR:-/var/tmp/portage-release}
SOURCE_DIR=${RELEASE_BUILDDIR}/checkout
BRANCH=${BRANCH:-trunk}
REPOSITORY=git@gitorious.org:neuvoo/portage.git
BRANCH="master"
CREATE_TAG=
CHANGELOG_REVISION=
UPLOAD_LOCATION=

die() {
	echo $@
	echo "Usage: ${0##*/} [--anon] [--branch <branch>] [--changelog-rev <rev>] [-t|--tag] [-u|--upload <location>] [--use-checkout <path>] <version>"
	exit 1
}

ARGS=$(getopt -o tu: --long anon,branch:,changelog-rev:,tag,upload:,use-checkout: \
	-n ${0##*/} -- "$@")
[ $? != 0 ] && die "initialization error"

eval set -- "${ARGS}"

while true; do
	case "$1" in
		--anon)
			REPOSITORY=git://gitorious.org/neuvoo/portage.git
			shift
			;;
		--changelog-rev)
			CHANGELOG_REVISION=$2
			shift 2
			;;
		--branch)
			BRANCH=$2
			shift 2
			;;
		--use-checkout)
			NO_REMOTE=true
			SOURCE_DIR=$2
			shift 2
			;;
		-t|--tag)
			CREATE_TAG=true
			shift
			;;
		-u|--upload)
			UPLOAD_LOCATION=${2}
			shift 2
			;;
		--)
			shift
			break
			;;
		*)
			die "unknown option: $1"
			;;
	esac
done

[ -z "$1" ] && die "Need version argument"
[ -n "${1/[0-9]*}" ] && die "Invalid version argument"

VERSION=${1}
RELEASE=portage-${VERSION}
RELEASE_DIR=${RELEASE_BUILDDIR}/${RELEASE}
RELEASE_TARBALL="${RELEASE_BUILDDIR}/${RELEASE}.tar.bz2"

echo ">>> Cleaning working directory ${RELEASE_DIR}"
rm -rf "${RELEASE_DIR}" || die "directory cleanup failed"
mkdir -p "${RELEASE_DIR}" || die "directory creation failed"
if [ ! -n "${NO_REMOTE}" ]; then
	echo ">>> Cleaning working directory ${SOURCE_DIR}"
	rm -rf "${SOURCE_DIR}" || die "directory cleanup failed"
	mkdir -p "${SOURCE_DIR}" || die "directory creation failed"
fi
cd "${SOURCE_DIR}" || die "SOURCE_DIR doesn't exist?"

if [ ! -n "${NO_REMOTE}" ]; then
	echo ">>> Starting Git export"
	git clone "${REPOSITORY}" || die "git clone failed"
	gitarchive_opts=""
	[ -n "$CHANGELOG_REVISION" ] && gitarchive_opts=+="${CHANGELOG_REVISION}"
	git archive $gitarchive_opts | tar -x -C "${SOURCE_DIR}" || die "git export failed"
fi

echo ">>> Creating Changelog"
gitlog_opts=""
[ -n "$CHANGELOG_REVISION" ] && gitlog_opts+=" -r ${CHANGELOG_REVISION}..HEAD"
git log $gitlog > "${SOURCE_DIR}/ChangeLog" || die "ChangeLog creation failed"

echo ">>> Building release tree"
cp -a "${SOURCE_DIR}/"{bin,cnf,doc,man,pym,src} "${RELEASE_DIR}/" || die "directory copy failed"
cp "${SOURCE_DIR}/"{ChangeLog,DEVELOPING,NEWS,RELEASE-NOTES,TEST-NOTES} \
	"${RELEASE_DIR}/" || die "file copy failed"

cd "${RELEASE_BUILDDIR}"

echo ">>> Creating release tarball ${RELEASE_TARBALL}"
tar --owner portage --group portage -cjf "${RELEASE_TARBALL}" "${RELEASE}" || \
	die "tarball creation failed"

DISTDIR=$(portageq distdir)
if [ -n "${DISTDIR}" -a -d "${DISTDIR}" -a -w "${DISTDIR}" ]; then
	echo ">>> Copying release tarball into ${DISTDIR}"
	cp "${RELEASE_TARBALL}" "${DISTDIR}"/ || echo "!!! tarball copy failed"
fi

if [ -n "${UPLOAD_LOCATION}" ]; then
	echo ">>> Uploading ${RELEASE_TARBALL} to ${UPLOAD_LOCATION}"
	scp "${RELEASE_TARBALL}" "dev.gentoo.org:${UPLOAD_LOCATION}" || die "upload failed"
else
	echo "${RELEASE_TARBALL} created"
fi

if [ -n "${CREATE_TAG}" ]; then
	echo ">>> Tagging ${VERSION} in repository"
	echo "Tagging not written yet."
	echo "Please tag ${REPOSITORY}/tags/${VERSION} by hand" # TODO
#	echo ">>> Tagging ${VERSION} in repository"
#	svn cp ${SVN_LOCATION} ${REPOSITORY}/tags/${VERSION} || die "tagging failed"
fi

