RPM_SPEC_FILES := rpm_spec/qubes-video-companion.spec

ifeq ($(PACKAGE_SET),dom0)
RPM_SPEC_FILES := rpm_spec/qubes-video-companion-dom0.spec
endif

DEBIAN_BUILD_DIRS := debian
