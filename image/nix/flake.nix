{
  description = "Pinned runtime closure for the integrated HPC development shell";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  outputs = { self, nixpkgs }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; };
      tools = {
        bash = pkgs.bashInteractive;
        bat = pkgs.bat;
        fd = pkgs.fd;
        fzf = pkgs.fzf;
        rg = pkgs.ripgrep;
        jq = pkgs.jq;
        nvim = pkgs.neovim-unwrapped;
        tmux = pkgs.tmux;
        eza = pkgs.eza;
        zoxide = pkgs.zoxide;
        less = pkgs.less;
        tput = pkgs.ncurses;
        infocmp = pkgs.ncurses;
      };
      versions = pkgs.lib.mapAttrs (_: p: { version = pkgs.lib.getVersion p; store = toString p; }) tools;
      toolbox = pkgs.runCommand "hpc-workspace-toolbox" {
        nativeBuildInputs = [ pkgs.patchelf ];
      } ''
        mkdir -p $out/bin $out/libexec $out/share $out/manifests
        harden() {
          cp -L "$1" "$2"
          chmod u+w "$2"
          if patchelf --print-interpreter "$2" >/dev/null 2>&1; then
            patchelf --force-rpath --set-rpath "$(patchelf --print-rpath "$2")" "$2"
          fi
        }
        ${pkgs.lib.concatStringsSep "\n" (pkgs.lib.mapAttrsToList (name: pkg:
          "harden ${pkg}/bin/${name} $out/${if name == "nvim" then "libexec" else "bin"}/${name}") tools)}
        ln -s /workspace-tools/thin-nvim $out/bin/nvim
        harden ${pkgs.python3}/bin/python3 $out/libexec/python3
        ln -s ${pkgs.bash-completion}/share/bash-completion $out/share/bash-completion
        ln -s ${pkgs.fzf}/share/fzf $out/share/fzf
        ln -s ${pkgs.ncurses}/share/terminfo $out/share/terminfo
        ln -s ${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt $out/share/ca-bundle.crt
        printf '%s\n' '${pkgs.python3Packages.pyyaml}/${pkgs.python3.sitePackages}' > $out/manifests/yaml-path.txt
        printf '%s\n' '${builtins.toJSON versions}' > $out/manifests/tools.json
        printf '%s\n' '${pkgs.python3}' > $out/manifests/python-prefix.txt
      '';
    in { packages.x86_64-linux.default = toolbox; };
}
