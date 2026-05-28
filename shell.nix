{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python3;
  pythonWithPackages = python.withPackages (ps: with ps; [
    fastapi
    uvicorn
    python-dotenv
    python-multipart
    pydantic
    boto3
    pytest
    httpx
    psycopg2
    pip
    setuptools
    wheel
  ]);
in
pkgs.mkShell {
  packages = [
    pythonWithPackages
    pkgs.libpq
    pkgs.openssl
    pkgs.zlib
    pkgs.git
  ];

  shellHook = ''
    echo "BudgetBot nix-shell ready."
    echo "Run: pip install -r requirements.txt  # installs missing PyPI-only deps (e.g., mangum)"
  '';
}
