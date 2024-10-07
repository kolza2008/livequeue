{pkgs}: {
  deps = [
    pkgs.cacert
    pkgs.openssl
    pkgs.libxcrypt
    pkgs.postgresql
  ];
}
