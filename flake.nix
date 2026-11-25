{
  description = "Custom test GTK4 app";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    pythonPkgs = pkgs.python3.withPackages (ps: with ps; [ pygobject3 ]);
  in {
    packages.${system}.default = pkgs.stdenv.mkDerivation {
      pname = "pretested";
      version = "1.0.0";
      src = ./.;

      nativeBuildInputs = [
        pkgs.gobject-introspection
        pkgs.wrapGAppsHook4
      ];

      buildInputs = [
        pythonPkgs
        pkgs.gtk4
      ];

      # Every copy below is load-bearing. An earlier version suffixed each with
      # `|| true`, which turned a missing style.css or question bank into a
      # silently broken package instead of a build failure.
      installPhase = ''
        runHook preInstall

        mkdir -p $out/bin $out/lib
        mkdir -p $out/share/applications
        mkdir -p $out/share/icons/hicolor/scalable/apps
        mkdir -p $out/share/pretested/subjects

        cp -r pretested $out/lib/
        rm -rf $out/lib/pretested/__pycache__
        install -Dm644 data/subjects/*.json -t $out/share/pretested/subjects/

        cat > $out/bin/pretested <<EOF
#!${pythonPkgs}/bin/python3
import sys
sys.path.insert(0, "$out/lib")
from pretested.app import main
sys.exit(main())
EOF
        chmod +x $out/bin/pretested

        install -Dm644 pretested.desktop -t $out/share/applications/
        install -Dm644 icon.svg $out/share/icons/hicolor/scalable/apps/pretested.svg

        runHook postInstall
      '';

      meta = with pkgs.lib; {
        description = "GTK4 app for drilling multiple-choice exam banks";
        mainProgram = "pretested";
        platforms = platforms.linux;
      };
    };

    devShells.${system}.default = pkgs.mkShell {
      packages = [
        pythonPkgs
        pkgs.gtk4
        pkgs.gobject-introspection
      ];
    };
  };
}