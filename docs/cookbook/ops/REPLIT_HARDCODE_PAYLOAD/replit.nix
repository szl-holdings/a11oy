{ pkgs }: {
  deps = [
    pkgs.bash
    pkgs.gh
    pkgs.jq
    pkgs.curl
    pkgs.git
    pkgs.gnused
    pkgs.gnugrep
    pkgs.coreutils
    pkgs.gawk
    pkgs.findutils
    pkgs.python311
    pkgs.cacert
  ];
}
