RPM_SPEC_FILES := rpm_spec/qubes-video-companion.spec

ifeq ($(PACKAGE_SET),dom0)
RPM_SPEC_FILES := rpm_spec/qubes-video-companion-dom0.spec
endif

DEBIAN_BUILD_DIRS := debian

ifeq ($(PACKAGE_SET),vm)
ARCH_BUILD_DIRS := archlinux
endif

# Support for new packaging
ifneq ($(filter $(DISTRIBUTION), archlinux),)
VERSION := $(file <$(ORIG_SRC)/$(DIST_SRC)/version)
GIT_TARBALL_NAME ?= qubes-video-companion-$(VERSION)-1.tar.gz
SOURCE_COPY_IN := source-archlinux-copy-in

source-archlinux-copy-in: PKGBUILD = $(CHROOT_DIR)/$(DIST_SRC)/$(ARCH_BUILD_DIRS)/PKGBUILD
source-archlinux-copy-in:
	cp $(PKGBUILD).in $(CHROOT_DIR)/$(DIST_SRC)/PKGBUILD
	sed -i "s/@VERSION@/$(VERSION)/g" $(CHROOT_DIR)/$(DIST_SRC)/PKGBUILD
	sed -i "s/@REL@/1/g" $(CHROOT_DIR)/$(DIST_SRC)/PKGBUILD
endif

# vim: filetype=make
