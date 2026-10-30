{ lib }:
lib.cleanSourceWith {
  src = ./repository;
  filter = path: type:
    let name = builtins.baseNameOf path; in
    !(builtins.elem name [ "__pycache__" ".venv" ".local" ".git" ])
    && !(lib.hasSuffix ".pyc" name);
}
