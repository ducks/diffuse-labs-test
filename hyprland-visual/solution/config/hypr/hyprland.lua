hl.monitor({output="", mode="1280x720@60", position="auto", scale=1})
hl.config({
  general={gaps_in=10,gaps_out=24,border_size=3,layout="dwindle",
    col={active_border="rgb(d79921)",inactive_border="rgb(504945)"}},
  decoration={rounding=12,blur={enabled=false},shadow={enabled=false}},
  animations={enabled=false},
  input={follow_mouse=0},
  misc={disable_hyprland_logo=true,disable_splash_rendering=true,background_color="rgb(1d2021)"},
})
hl.bind("SUPER + Return", hl.dsp.exec_cmd("desktop-terminal"))
hl.bind("SUPER + Space", hl.dsp.exec_cmd("desktop-launcher"))
hl.bind("SUPER + Q", hl.dsp.window.close())
for i=1,3 do hl.bind("SUPER + " .. i, hl.dsp.focus({workspace=i})) end
hl.on("hyprland.start", function() hl.exec_cmd("waybar") end)
