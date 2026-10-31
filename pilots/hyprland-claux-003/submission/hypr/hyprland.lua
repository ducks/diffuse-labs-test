-- Working starting desktop. Match the target screenshots by editing config/.
hl.monitor({output="", mode="1280x720@60", position="auto", scale=1})
hl.config({animations={enabled=false}, misc={disable_hyprland_logo=true,disable_splash_rendering=true}})
hl.bind("SUPER + Return", hl.dsp.exec_cmd("desktop-terminal"))
hl.bind("SUPER + Space", hl.dsp.exec_cmd("desktop-launcher"))
hl.bind("SUPER + Q", hl.dsp.window.close())
for i=1,3 do hl.bind("SUPER + " .. i, hl.dsp.focus({workspace=i})) end
hl.on("hyprland.start", function() hl.exec_cmd("waybar") end)
