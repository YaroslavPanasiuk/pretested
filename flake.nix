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

        mkdir -p $out/bin
        mkdir -p $out/share/applications
        mkdir -p $out/share/icons/hicolor/scalable/apps
        mkdir -p $out/share/pretested

        install -Dm644 model.py ui.py -t $out/bin/
        install -Dm644 style.css -t $out/bin/
        install -Dm755 main.py $out/bin/pretested

        install -Dm644 tests.json -t $out/share/pretested/
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