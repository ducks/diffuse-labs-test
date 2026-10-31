{ configDir }:
{ lib, pkgs, ... }:
let
  shellrc = pkgs.writeText "visual-desktop-bashrc" ''
    PS1='$ '
    unset PROMPT_COMMAND HISTFILE
  '';
  terminal = pkgs.writeShellScriptBin "desktop-terminal" ''
    exec ${pkgs.foot}/bin/foot --app-id=visual-terminal --title=Terminal ${pkgs.bashInteractive}/bin/bash --noprofile --rcfile ${shellrc}
  '';
  card = pkgs.writeShellScriptBin "desktop-card" ''
    label="''${1:-Workspace}"
    exec ${pkgs.foot}/bin/foot --app-id=visual-card --title="$label" \
      ${pkgs.bashInteractive}/bin/bash --noprofile --norc -c '
        printf "\n  %s\n  ------------------------\n\n" "$1"
        printf "  configure / capture / compare\n\n"
        printf "  Hyprland visual laboratory\n  deterministic desktop fixture\n\n"
        exec bash --noprofile --rcfile ${shellrc}
      ' bash "$label"
  '';
  launcher = pkgs.writeShellScriptBin "desktop-launcher" ''
    selection=$(printf 'Terminal\nNotes\nFiles\n' | ${pkgs.wofi}/bin/wofi --dmenu --prompt Launch) || exit 0
    case "$selection" in
      Terminal) exec ${terminal}/bin/desktop-terminal ;;
      Notes) exec ${card}/bin/desktop-card Notes ;;
      Files) exec ${card}/bin/desktop-card Files ;;
    esac
  '';
in {
  system.stateVersion = "25.11";
  virtualisation = {
    memorySize = 2048;
    cores = 2;
    diskSize = 2048;
    qemu.options = [ "-vga none -device virtio-gpu-pci" ];
    restrictNetwork = lib.mkForce true;
  };
  networking.useDHCP = lib.mkForce false;
  networking.interfaces.eth0.useDHCP = lib.mkForce false;
  programs.hyprland.enable = true;
  users.users.desktop = {
    isNormalUser = true;
    uid = 1000;
    extraGroups = [ "video" "render" ];
  };
  fonts = {
    packages = [ pkgs.dejavu_fonts ];
    fontconfig.defaultFonts = {
      monospace = [ "DejaVu Sans Mono" ];
      sansSerif = [ "DejaVu Sans" ];
    };
  };
  environment.systemPackages = [
    pkgs.grim pkgs.foot pkgs.waybar pkgs.wofi pkgs.jq pkgs.python3
    terminal card launcher
  ];
  environment.variables = {
    LIBGL_ALWAYS_SOFTWARE = "1";
    AQ_NO_MODIFIERS = "1";
    XCURSOR_SIZE = "24";
    PS1 = "$ ";
    LC_ALL = "C.UTF-8";
  };
  environment.etc."desktop-config".source = builtins.path {
    path = configDir;
    name = "hyprland-user-config";
  };
  systemd.tmpfiles.rules = [
    "L+ /home/desktop/.config - - - - /etc/desktop-config"
  ];
  services.greetd = {
    enable = true;
    settings = let
      session = {
        user = "desktop";
        command = "${pkgs.hyprland}/bin/start-hyprland -- --config /home/desktop/.config/hypr/hyprland.lua";
      };
    in { initial_session = session; default_session = session; };
  };
}
