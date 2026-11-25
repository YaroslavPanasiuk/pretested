{
  description = "GTK4 app for drilling multiple-choice exam banks";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    python3Packages = pkgs.python3Packages;
    pythonPkgs = pkgs.python3.withPackages (ps: with ps; [ pygobject3 pytest ]);
  in {
    packages.${system}.default = python3Packages.buildPythonApplication {
      pname = "pretested";
      version = "2.0.0";
      src = ./.;
      pyproject = true;

      build-system = [ python3Packages.setuptools ];
      dependencies = [ python3Packages.pygobject3 ];

      nativeBuildInputs = [
        pkgs.gobject-introspection
        pkgs.wrapGAppsHook4
      ];

      buildInputs = [ pkgs.gtk4 ];

      # wrapGAppsHook4 and the Python wrapper would otherwise wrap the entry
      # point twice; the nixpkgs idiom is to let makeWrapper do it once with
      # the GApps arguments folded in.
      dontWrapGApps = true;
      makeWrapperArgs = [ "\${gappsWrapperArgs[@]}" ];

      # library, attempt and results import no GTK, so the suite runs here
      # without a display.
      nativeCheckInputs = [ python3Packages.pytestCheckHook ];

      postInstall = ''
        install -Dm644 data/subjects/*.json -t $out/share/pretested/subjects/
        install -Dm644 pretested.desktop -t $out/share/applications/
        install -Dm644 icon.svg $out/share/icons/hicolor/scalable/apps/pretested.svg
      '';

      meta = with pkgs.lib; {
        description = "GTK4 app for drilling multiple-choice exam banks";
        mainProgram = "pretested";
        platforms = platforms.linux;
      };
    };

    checks.${system} = {
      # Builds the package, which runs the suite in its check phase.
      package = self.packages.${system}.default;

      # A standalone run of the suite, needing no GTK closure.
      pytest = pkgs.runCommand "pretested-pytest" {
        nativeBuildInputs = [ python3Packages.pytest ];
      } ''
        cp -r ${./.} src
        chmod -R +w src
        cd src
        pytest
        touch $out
      '';
    };

    devShells.${system}.default = pkgs.mkShell {
      packages = [
        pythonPkgs
        pkgs.gtk4
        pkgs.gobject-introspection
        pkgs.xvfb-run
      ];
    };
  };
}
