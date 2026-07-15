{
  description = "School test GTK4 app";
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

      installPhase = ''
        mkdir -p $out/bin
        mkdir -p $out/share/applications
        mkdir -p $out/share/icons/hicolor/scalable/apps
        mkdir -p $out/share/pretested
        
        cp *.py $out/bin/
        
        cp style.css $out/bin/ 2>/dev/null || true
        cp tests.json $out/share/pretested/ 2>/dev/null || true
        
        mv $out/bin/main.py $out/bin/pretested
        chmod +x $out/bin/pretested
        
        cp pretested.desktop $out/share/applications/ 2>/dev/null || true
        cp icon.svg $out/share/icons/hicolor/scalable/apps/pretested.svg 2>/dev/null || true
      '';
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