# Transfer and start the workspace

These are the retained **0.4 core-image** instructions. For the integrated thin release and automated installer, use the [thin startup guide](thin-start.md).

This workflow uses a public GitHub repository and downloadable release files. It does not require a container registry or Docker on the cluster. Build and test on the workstation, then transfer the same SIF and launcher bundle to Ruth, Jean, and Blueback.

## 1. Download the release

Open [release 0.4.0-preview1](https://github.com/ray12514/hpc-workspace/releases/tag/v0.4.0-preview1) on your workstation and download these four assets:

| File | Purpose |
| --- | --- |
| [hpc-workspace-core-0.4.0-preview1-linux-amd64.sif](https://github.com/ray12514/hpc-workspace/releases/download/v0.4.0-preview1/hpc-workspace-core-0.4.0-preview1-linux-amd64.sif) | Ready-to-run Linux amd64 container, about 600 MiB |
| [SIF checksum](https://github.com/ray12514/hpc-workspace/releases/download/v0.4.0-preview1/hpc-workspace-core-0.4.0-preview1-linux-amd64.sif.sha256) | Checks the image after transfer |
| [hpc-workspace-source-0.4.0-preview1.tar.gz](https://github.com/ray12514/hpc-workspace/releases/download/v0.4.0-preview1/hpc-workspace-source-0.4.0-preview1.tar.gz) | Launcher, generic profiles, session configuration, documentation, and build recipes |
| [Source checksum](https://github.com/ray12514/hpc-workspace/releases/download/v0.4.0-preview1/hpc-workspace-source-0.4.0-preview1.tar.gz.sha256) | Checks the launcher bundle after transfer |

Use the explicitly named source bundle above. GitHub also generates its own source archives; their bytes and directory names differ from this bundle.

The release also includes installed-package manifests and a machine-readable release record. They are useful for inspecting the build but are not needed to start it. The Docker archive is retained on the builder and is not part of this transfer release.

## 2. Transfer the files

On each cluster, choose a new, persistent directory with room for the four files and extracted source. For the examples below, create:

```bash
mkdir -p "$HOME/hpc-workspace-releases/0.4.0-preview1"
```

Transfer the four files into that directory using your site's approved transfer method. You can also download the release files directly on a cluster where GitHub downloads are allowed. No upload of cluster files or reports is involved.

## 3. Verify and unpack on the cluster

Run these commands in the transfer directory. Continue only if both checks report `OK`:

```bash
cd "$HOME/hpc-workspace-releases/0.4.0-preview1"
sha256sum -c hpc-workspace-core-0.4.0-preview1-linux-amd64.sif.sha256
sha256sum -c hpc-workspace-source-0.4.0-preview1.tar.gz.sha256
```

Extract into this new release directory and make its launcher available in the current shell:

```bash
tar --keep-old-files -xzf hpc-workspace-source-0.4.0-preview1.tar.gz
export PATH="$HOME/hpc-workspace-releases/0.4.0-preview1/hpc-workspace/bin:$PATH"
```

Do not extract over an existing installation. If you already unpacked this release, keep that directory and skip extraction. The host needs Python 3.6+ and the site's Apptainer module. Load Apptainer using the site's normal instructions; the initial runtime target is 1.3.6 through 1.5.

## 4. Select the image and enter

Run from the release directory used above. If an existing Inspector YAML is available locally, import it once using the verified new image:

```bash
ws init --profile /path/to/local/profile.yaml \
  --image "$PWD/hpc-workspace-core-0.4.0-preview1-linux-amd64.sif"
```

Otherwise, save an original system default with `ws init --site ruth`, using `jean` or `blueback` where appropriate. Inspector is optional. Then select the verified image:

```bash
ws use \
  "$PWD/hpc-workspace-core-0.4.0-preview1-linux-amd64.sif" \
  --sha256 "$(cut -d ' ' -f 1 hpc-workspace-core-0.4.0-preview1-linux-amd64.sif.sha256)"
```

Then enter with an existing project directory, replacing the example path:

```bash
ws enter --project "$HOME/my-project"
```

The default selection is stored separately for each configured system. The container uses your normal user identity and binds your home and chosen project. Exit and re-enter to check that your project edits and editor state persist. Keep personal mounts in the saved configuration's `overrides` or the extracted source's `profiles/SITE.local.json`. The [import guide](inspector-integration.md) explains both. All imported facts and personal settings remain local.

For future shells, add the `export PATH=...` line above to your own shell configuration, or invoke this release's `hpc-workspace/bin/ws` by its full path. `ws init` writes workspace configuration; it does not edit shell startup files.

This release is a preview: local Docker and extracted-SIF checks passed, but normal SIF mounting on these clusters has not been tested. Perform the first launch locally on each site before adopting it. See [the validation record](validation.md) for the exact scope. CUDA/ROCm toolkits and host MPI integration are later extensions.

## 5. Sessions, allocations, and updates

On a stable login host, `ws session --project "$HOME/my-project" --host-jobs` starts the persistent project layout. It requires host tmux and enables the local connection for `ws submit` and `ws jobs` inside the workspace. See the [historical core workflow](legacy/core-workflow.md) for submission and PuTTY/VS Code appearance settings. Request an interactive allocation from its host-shell window using the site's normal workflow, then run `ws enter --compute --project "$HOME/my-project"` inside that allocation.

For an update, transfer the new release into a new directory, verify its files, and unpack its matching launcher. Copy any needed site-local profile directly between local installations on that cluster. Update your launcher path and use `ws use` with the new image and checksum. Keep the previous release directory: `ws rollback --site SITE` can select its image again. Running sessions continue to use their existing image; use the matching older launcher if rolling back a launcher change. Batch jobs should specify a full, versioned `--image` path.

Saved workspace configuration is outside the release directory and survives launcher/image updates. When the system changes, update its YAML using your existing Inspector workflow, then use `ws refresh --dry-run` and `ws refresh`. This refresh preserves personal overrides, image selections, and saved state. It does not run Inspector or rebuild the image.

Release 0.4.0-preview1 also creates missing personal dotfile starters under `~/.config/hpc-workspace/` on entry. Your existing preferences and local `config.json` are preserved. Shared defaults follow the selected image through the starter include/loader files; see the [core dotfile guide](legacy/core-dotfiles.md) before replacing those loaders with a complete personal configuration.
