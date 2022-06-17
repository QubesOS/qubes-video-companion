FROM fedora:35

ARG pkg_name
ENV pkg_name=$pkg_name

WORKDIR /
RUN dnf install -y rpm-build rpmdevtools pandoc make

COPY . /$pkg_name/

RUN tar czf $pkg_name.tar.gz $pkg_name
RUN rpmdev-setuptree
RUN mv $pkg_name.tar.gz /root/rpmbuild/SOURCES
RUN cp /$pkg_name/rpm_spec/*.spec.in /root/rpmbuild/SPECS
