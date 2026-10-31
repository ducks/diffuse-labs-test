"""Public desktop capture helpers, executed by the NixOS Python test driver."""
import base64
import io
import json
import os
from pathlib import Path
import shlex
import time

from PIL import Image, ImageChops, ImageStat

instance = None
captures = Path(os.environ.get('out', '.')) / 'captures'
captures.mkdir(exist_ok=True, parents=True)


def user(command):
    env = 'export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1; '
    if instance:
        env += 'export HYPRLAND_INSTANCE_SIGNATURE=' + shlex.quote(instance) + '; '
    return desktop.succeed('su - desktop -c ' + shlex.quote(env + command))


def ctl(command):
    return user('hyprctl ' + command)


def ready():
    global instance
    desktop.wait_for_unit('multi-user.target')
    desktop.wait_until_succeeds("su - desktop -c 'XDG_RUNTIME_DIR=/run/user/1000 hyprctl -j instances | grep instance'", timeout=90)
    instance = json.loads(user('hyprctl -j instances'))[0]['instance']
    monitors = json.loads(ctl('-j monitors'))
    assert len(monitors) == 1 and (monitors[0]['width'], monitors[0]['height']) == (1280, 720)
    assert not ctl('configerrors').strip(), 'Hyprland configuration errors'
    try:
        until(lambda: 'waybar' in ctl('-j layers'), 'Waybar layer', timeout=25)
    except Exception:
        print(desktop.succeed('journalctl -u greetd --no-pager -n 100'))
        print(desktop.succeed('ps -u desktop -o pid,comm,args'))
        raise


def clients():
    return json.loads(ctl('-j clients'))


def until(predicate, description, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.15)
    print('TIMEOUT_DIAGNOSTICS ' + description)
    print(ctl('-j clients'))
    print(ctl('-j layers'))
    print(desktop.succeed('journalctl -u greetd --no-pager -n 70'))
    raise AssertionError('Timed out: ' + description)


def screenshot():
    user('grim /tmp/visual-frame.png')
    data = base64.b64decode(desktop.succeed('base64 -w0 /tmp/visual-frame.png'))
    frame = Image.open(io.BytesIO(data)).convert('RGB')
    assert frame.size == (1280, 720)
    # Keep pointer placement from dominating otherwise stable captures.
    frame.paste((0, 0, 0), (1248, 688, 1280, 720))
    return frame


def difference(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (3 * 255)


def capture(name):
    ctl('dispatch ' + shlex.quote('hl.dsp.cursor.move({x=1279,y=719})'))
    previous = screenshot()
    consecutive = 0
    for _ in range(35):
        time.sleep(0.15)
        current = screenshot()
        consecutive = consecutive + 1 if difference(previous, current) < 0.0004 else 0
        if consecutive >= 2:
            current.save(captures / (name + '.png'))
            return current
        previous = current
    raise AssertionError('Desktop did not settle: ' + name)


def scene(prefix=''):
    ctl('dispatch ' + shlex.quote('hl.dsp.focus({workspace=1})'))
    assert not clients(), 'Unexpected autostart windows'
    capture(prefix + 'empty')
    ctl('eval ' + shlex.quote('hl.exec_cmd("desktop-card Workspace")'))
    until(lambda: len(clients()) == 1, 'first fixture window')
    ctl('eval ' + shlex.quote('hl.exec_cmd("desktop-card Notes")'))
    until(lambda: len(clients()) == 2, 'second fixture window')
    until(lambda: all(c['size'][0] > 100 for c in clients()), 'window layout')
    tiled = capture(prefix + 'tiled')
    desktop.send_key('meta_l-spc')
    until(lambda: 'wofi' in ctl('-j layers'), 'launcher layer')
    # A registered layer can exist before its first buffer is painted. Merely
    # observing two unchanged frames can otherwise capture the old desktop.
    until(lambda: difference(tiled, screenshot()) > 0.0005, 'launcher has painted')
    capture(prefix + 'launcher')
