{
  description = "XC Cup Ranker - tool to rank XC Cup results";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python311;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            # Python
            python
            uv

            # Selenium deps (versions pinned together via nix)
            firefox
            geckodriver

            # Dev tools
            ruff

            # Misc
            just
          ];
        };
      });
}
