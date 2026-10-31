{ images ? [] }:
{ lib, pkgs, ... }:
let tools = import ./toolchain.nix;
in {
  system.stateVersion = "25.11";
  virtualisation = { memorySize = 4096; cores = 2; diskSize = 8192; restrictNetwork = lib.mkForce true; };
  networking.useDHCP = lib.mkForce false;
  networking.interfaces.eth0.useDHCP = lib.mkForce false;
  networking.firewall.enable = false;
  boot.kernelModules = [ "br_netfilter" "overlay" ];
  boot.kernel.sysctl."net.ipv4.ip_forward" = 1;
  services.k3s = {
    enable = true;
    role = "server";
    images = [ pkgs.k3s.airgap-images ] ++ images;
    extraFlags = [ "--disable=traefik" "--disable=servicelb" "--disable=metrics-server"
      "--node-ip=192.168.1.1" "--advertise-address=192.168.1.1" "--flannel-iface=eth1" ];
  };
  environment.systemPackages = [ tools.terraform pkgs.kubectl pkgs.python3 pkgs.curl pkgs.jq ];
  environment.variables = { KUBECONFIG = "/etc/rancher/k3s/k3s.yaml"; CHECKPOINT_DISABLE = "1"; };
}
