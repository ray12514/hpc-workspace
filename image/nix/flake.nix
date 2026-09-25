{
  description = "Pinned runtime closure for the integrated HPC development shell";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  outputs = { self, nixpkgs }:
    let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
        config.allowUnfreePredicate = p: pkgs.lib.getName p == "claude-code";
      };
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
        delta = pkgs.delta;
        lazygit = pkgs.lazygit;
        ncdu = pkgs.ncdu;
        spf = pkgs.superfile;
        tldr = pkgs.tealdeer;
        just = pkgs.just;
        uv = pkgs.uv;
        ruff = pkgs.ruff;
        yq = pkgs.yq-go;
        mlr = pkgs.miller;
        lnav = pkgs.lnav;
        direnv = pkgs.direnv;
        watchexec = pkgs.watchexec;
        hyperfine = pkgs.hyperfine;
        btop = pkgs.btop;
        difft = pkgs.difftastic;
        htop = pkgs.htop;
        shellcheck = pkgs.shellcheck;
        shfmt = pkgs.shfmt;
        gum = pkgs.gum;
      };
      editorTools = {
        bash-language-server = pkgs.bash-language-server;
        basedpyright = pkgs.basedpyright;
        fortls = pkgs.fortls;
      };
      agentTools = { codex = pkgs.codex; claude = pkgs.claude-code; };
      parsers = p: with p; [ c cpp fortran python bash json yaml lua markdown markdown_inline cmake vim vimdoc ];
      plugins = with pkgs.vimPlugins; [
        fzf-lua which-key-nvim gitsigns-nvim blink-cmp conform-nvim
        (nvim-treesitter.withPlugins parsers) vim-tmux-navigator
      ];
      pluginBundle = pkgs.vimUtils.packDir { workspace = { start = plugins; opt = []; }; };
      helpRevision = "41eaae631b5ee8a21f8aab5276c899036f91c28a";
      helpPages = pkgs.fetchurl {
        url = "https://codeload.github.com/tldr-pages/tldr/tar.gz/${helpRevision}";
        sha256 = "a6d566566815f77a8d55cbcd2ef5e738c8194bb7523a43efaffccaee46caac9b";
      };
      packageInfo = p: {
        version = pkgs.lib.getVersion p;
        license = map (l: l.spdxId or l.shortName) (pkgs.lib.toList (p.meta.license or []));
      };
      versions = pkgs.lib.mapAttrs (_: packageInfo) (tools // editorTools // agentTools);
      toolbox = pkgs.runCommand "hpc-workspace-toolbox" {
        nativeBuildInputs = [ pkgs.patchelf ];
      } ''
        mkdir -p $out/bin $out/libexec $out/share $out/manifests $out/agent-bin
        harden() {
          cp -L "$1" "$2"
          chmod u+w "$2"
          if patchelf --print-interpreter "$2" >/dev/null 2>&1; then
            # Preserve the existing string/ELF layout; enlarging Go executable
            # RPATHs caused startup crashes in the runtime regression fixture.
            patchelf --force-rpath --set-rpath "$(patchelf --print-rpath "$2")" "$2"
          fi
        }
        ${pkgs.lib.concatStringsSep "\n" (pkgs.lib.mapAttrsToList (name: pkg:
          "harden ${pkg}/bin/${if name == "spf" then "superfile" else name} $out/${if builtins.elem name [ "nvim" "spf" "lazygit" "btop" "tldr" "uv" "lnav" ] then "libexec" else "bin"}/${name}") tools)}
        ln -s /workspace-tools/thin-nvim $out/bin/nvim
        for name in spf lazygit btop tldr uv lnav; do ln -s /workspace-tools/thin-app $out/bin/$name; done
        # curl's own RUNPATH can still admit host SSL libraries. Scope the
        # complete dependency path to lnav's loader, preserving LD_LIBRARY_PATH
        # for any native child program instead of rewriting that environment.
        lnavLoader=$(patchelf --print-interpreter ${pkgs.lnav}/bin/lnav)
        lnavLibraries=$("$lnavLoader" --list ${pkgs.lnav}/bin/lnav | awk '/=> \/nix\/store\// { sub(/\/[^/]+$/, "", $3); print $3 }' | sort -u | paste -sd:)
        test -n "$lnavLibraries"
        printf '%s\n%s\n' "$lnavLoader" "$lnavLibraries" > $out/manifests/lnav-loader.txt
        # Catch these actual binary regressions before exporting a large image.
        $out/libexec/lazygit --version
        $out/libexec/spf --version
        $out/bin/mlr --version
        $out/bin/yq --version
        mkdir poison
        printf 'synthetic incompatible library\n' > poison/libssl.so.3
        LD_LIBRARY_PATH="$PWD/poison" "$lnavLoader" --library-path "$lnavLibraries" $out/libexec/lnav -V
        harden ${pkgs.python3}/bin/python3 $out/libexec/python3
        harden ${pkgs.nodejs}/bin/node $out/libexec/node
        # Use private hardened runtimes without changing host Python/Node or
        # exporting a replacement LD_LIBRARY_PATH to site compiler children.
        cp -L ${pkgs.fortls}/bin/fortls $out/libexec/fortls
        chmod u+w $out/libexec/fortls
        substituteInPlace $out/libexec/fortls \
          --replace '${pkgs.python3}/bin/python3' '/workspace-tools/libexec/python3'
        for name in bash-language-server basedpyright basedpyright-langserver; do
          ln -s /workspace-tools/thin-editor-tool $out/bin/$name
        done
        printf '%s\n' '${pkgs.bash-language-server}/lib/bash-language-server/server/out/cli.js' > $out/manifests/bash-language-server.txt
        find ${pkgs.basedpyright}/lib -name pyright.js > $out/manifests/basedpyright.txt
        find ${pkgs.basedpyright}/lib -name pyright-langserver.js > $out/manifests/basedpyright-langserver.txt
        test "$(wc -l < $out/manifests/basedpyright.txt)" -eq 1
        test "$(wc -l < $out/manifests/basedpyright-langserver.txt)" -eq 1
        ln -s /workspace-tools/libexec/fortls $out/bin/fortls
        harden ${pkgs.codex}/bin/.codex-wrapped $out/libexec/codex
        harden ${pkgs.codex}/bin/codex-code-mode-host $out/libexec/codex-code-mode-host
        harden ${pkgs.claude-code}/bin/.claude-wrapped $out/libexec/claude
        patchelf --force-rpath --add-rpath '${pkgs.lib.getLib pkgs.alsa-lib}/lib' $out/libexec/claude
        harden ${pkgs.bubblewrap}/bin/bwrap $out/agent-bin/bwrap
        harden ${pkgs.socat}/bin/socat $out/agent-bin/socat
        for name in codex claude; do ln -s /workspace-tools/thin-agent $out/bin/$name; done
        ln -s ${pkgs.bash-completion}/share/bash-completion $out/share/bash-completion
        ln -s ${pkgs.fzf}/share/fzf $out/share/fzf
        ln -s ${pkgs.ncurses}/share/terminfo $out/share/terminfo
        ln -s ${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt $out/share/ca-bundle.crt
        ln -s ${pkgs.glibcLocales}/lib/locale/locale-archive $out/share/locale-archive
        ln -s ${pluginBundle} $out/share/nvim
        mkdir -p help-source $out/share/tldr/tldr-pages/pages.en
        tar -xzf ${helpPages} --strip-components=1 -C help-source
        cp -r help-source/pages/common help-source/pages/linux $out/share/tldr/tldr-pages/pages.en/
        cp help-source/LICENSE.md $out/share/tldr/LICENSE.md
        printf '%s\n' '${helpRevision}' > $out/manifests/tldr-revision.txt
        printf '%s\n' '${builtins.toJSON (map packageInfo plugins)}' > $out/manifests/plugins.json
        printf '%s\n' '${pkgs.python3Packages.pyyaml}/${pkgs.python3.sitePackages}' > $out/manifests/yaml-path.txt
        printf '%s\n' '${pkgs.python3Packages.tomlkit}/${pkgs.python3.sitePackages}' > $out/manifests/toml-path.txt
        printf '%s\n' '${builtins.toJSON versions}' > $out/manifests/tools.json
        printf '%s\n' '${pkgs.python3}' > $out/manifests/python-prefix.txt
      '';
    in { packages.x86_64-linux.default = toolbox; };
}
