import secrets


def functionality():
    # Select a real application through the launcher, not through its helper.
    before = len(clients())
    desktop.send_chars('Terminal')
    capture('launcher-filtered')
    desktop.send_key('ret')
    until(lambda: len(clients()) == before + 1, 'launcher opens a terminal')
    assert 'wofi' not in ctl('-j layers')
    desktop.send_key('meta_l-q')
    until(lambda: len(clients()) == before, 'close-window shortcut')
    desktop.send_key('meta_l-ret')
    until(lambda: len(clients()) == before + 1, 'terminal shortcut')
    nonce = secrets.token_hex(12)
    desktop.send_chars('printf ' + nonce + ' > /tmp/keyboard-proof\n')
    until(lambda: desktop.execute('cat /tmp/keyboard-proof')[1].strip() == nonce, 'keyboard reaches the real shell')
    assert desktop.succeed('stat -c %u /tmp/keyboard-proof').strip() == '1000'
    desktop.send_key('meta_l-2')
    until(lambda: json.loads(ctl('-j activeworkspace'))['id'] == 2, 'workspace shortcut')
    assert all(c['workspace']['id'] == 1 for c in clients()), 'Switching workspace moved the windows'
    capture('workspace-two')


desktop.start()
with subtest('fresh desktop and three visual scenes'):
    ready()
    scene()
with subtest('launcher, terminal, close, keyboard, and workspace are functional'):
    functionality()
with subtest('cold boot recreates the same desktop'):
    boot = desktop.succeed('cat /proc/sys/kernel/random/boot_id').strip()
    desktop.shutdown()
    desktop.start()
    instance = None
    ready()
    assert desktop.succeed('cat /proc/sys/kernel/random/boot_id').strip() != boot
    scene('reboot-')

names = ['empty', 'tiled', 'launcher']
repeatability = {}
for name in names:
    error = difference(Image.open(captures / (name + '.png')), Image.open(captures / ('reboot-' + name + '.png')))
    repeatability[name] = error
    if not MAKE_TARGETS:
        assert error <= 0.001, 'Unstable visual scene across boots: ' + name

visual = {}
# Separate regions prevent a large matching background hiding a wrong bar or menu.
regions = {
    'empty': {'bar': (0, 0, 1280, 76), 'background': (0, 76, 1280, 688)},
    'tiled': {'bar': (0, 0, 1280, 76), 'left': (0, 76, 640, 688), 'right': (640, 76, 1280, 688),
              'left-edge': (20, 72, 630, 94), 'right-edge': (646, 72, 1260, 94)},
    'launcher': {'bar': (0, 0, 1280, 76), 'menu': (380, 190, 900, 530), 'outside': (0, 76, 350, 688)},
}
if not MAKE_TARGETS:
    with subtest('all visual regions match supplied targets'):
        for name, boxes in regions.items():
            target = Image.open(TARGETS / (name + '.png')).convert('RGB')
            for prefix in ['', 'reboot-']:
                actual = Image.open(captures / (prefix + name + '.png')).convert('RGB')
                for region, box in boxes.items():
                    error = difference(actual.crop(box), target.crop(box))
                    visual[prefix + name + '/' + region] = error
        print('VISUAL_REGION_ERRORS ' + json.dumps(visual))
        failures = {key: value for key, value in visual.items() if value > 0.012}
        assert not failures, 'Visual mismatch: ' + json.dumps(failures)

result = {'passed': all(value <= 0.001 for value in repeatability.values()), 'target_generation': MAKE_TARGETS,
          'reboot_normalized_rgb_mae': repeatability, 'target_region_normalized_rgb_mae': visual}
(captures.parent / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print('HYPRLAND_VISUAL_VERIFIED ' + json.dumps(result))
