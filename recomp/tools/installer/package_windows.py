"""Stage a media-free Windows player assistant and optionally build an installer.

Never packages the current game executable, generated game code, extracted
packs, cards or discs. The SDK contains authored source plus OpenBIOS under its
own license; game code/assets are reconstructed on the player's computer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT.parent
REJECT_EXTENSIONS = {'.bin', '.cue', '.img', '.iso', '.ccd', '.sub', '.mcd', '.mcr', '.pst', '.pack', '.exe', '.dll', '.log', '.bak', '.pyc'}


def files_in_git(root):
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--recurse-submodules', '-z'])
    untracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '-z'])
    files = {p for p in tracked.decode('utf-8').split('\0') if p}
    # Accept new authored implementation, never arbitrary untracked player data.
    files.update(p for p in untracked.decode('utf-8').split('\0')
                 if p and Path(p).suffix.lower() in {'.c', '.cpp', '.h', '.hpp', '.inc', '.py', '.cmake'})
    return sorted(files)


def private_file(path):
    return (path.suffix.lower() in REJECT_EXTENSIONS or
            re.search(r'\.(?:mcd|mcr|pst)(?:\.|$)', path.name, re.IGNORECASE) is not None)


def audit_sdk_path(path):
    value = path.as_posix()
    top = path.parts[1] if path.parts[:1] in [('psxrecomp',), ('recomp-ui',)] and len(path.parts)>1 else path.parts[0]
    if top in {'disc', 'saves', 'research', 'analysis', 'generated'} or any(p in {'.git', '__pycache__'}
           or p.startswith('build-') for p in path.parts):
        raise ValueError('Forbidden SDK path: ' + value)
    if private_file(path) and value != 'psxrecomp/bios/openbios.bin':
        raise ValueError('Forbidden media or extracted asset: ' + value)


def stage_sdk(stage, menu_glyphs=None):
    sdk = stage / 'sdk'
    sdk.mkdir()
    source_files = []
    top_files = {'CMakeLists.txt', 'CMakePresets.json', 'game.toml', 'game.local.toml',
                 'codegen_setup.c', 'codegen_setup.h', 'requirements-local.txt', 'VERSION', 'LICENSE'}
    for name in files_in_git(GAME):
        path = Path(name)
        if not path.parts or path.parts[0] != 'recomp':
            continue
        relative = Path(*path.parts[1:])
        if relative.as_posix() in top_files or relative.parts[:1] in [('src',), ('assets',), ('seeds',)] or relative.parts[:2] in [('tools', 'local'), ('tests', 'local'), ('mods', 'preloaded')]:
            if (ROOT / relative).is_file():
                source_files.append((ROOT / relative, relative))
    # Worktree changes (including the exported Windows renderer implementation)
    # are included, but nested build/media trees are never selected.
    for dependency in ('psxrecomp', 'recomp-ui'):
        base = ROOT / dependency
        for name in files_in_git(base):
            path = Path(name)
            if any(p in {'docs', 'doc', 'tests', 'test_data', 'generated', 'build', '__pycache__'} or p.startswith(('build-', '.')) for p in path.parts):
                continue
            if (base / path).is_file():
                source_files.append((base / path, Path(dependency) / path))
    if menu_glyphs is not None:
        glyph_path = Path('assets/ui/installer-menu-glyphs.png')
        source_files = [(source, path) for source, path in source_files if path != glyph_path]
        source_files.append((menu_glyphs, glyph_path))
    manifest = []
    for source, relative in source_files:
        if private_file(relative) and relative.as_posix() != 'psxrecomp/bios/openbios.bin':
            continue
        audit_sdk_path(relative)
        target = sdk / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest.append(dict(path=relative.as_posix(), sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    if not all((sdk / p).is_file() for p in ('game.local.toml', 'psxrecomp/runtime/src/render_worker_win.h',
                                           'psxrecomp/bios/OpenBIOS.LICENSE',
                                           'mods/preloaded/packages/dnttk.presentation.frame_rate/1.0.0/manifest.toml')):
        raise ValueError('Incomplete title SDK or Windows render helper missing')
    (sdk / 'sdk-manifest.json').write_text(json.dumps(dict(schema=1, files=manifest), indent=2), encoding='utf-8')


SYSTEM_DLLS = {'kernel32.dll', 'ntdll.dll', 'user32.dll', 'gdi32.dll', 'shell32.dll',
               'ole32.dll', 'oleaut32.dll', 'advapi32.dll', 'comdlg32.dll', 'opengl32.dll',
               'msvcrt.dll', 'ws2_32.dll', 'bcrypt.dll', 'crypt32.dll', 'version.dll',
               'shlwapi.dll', 'comctl32.dll', 'winmm.dll', 'rpcrt4.dll'}


def bundle_dlls(tools, kit):
    reader = kit / 'bin/llvm-readobj.exe'
    pending = list(tools.glob('*.exe'))
    seen = set()
    while pending:
        file = pending.pop()
        text = subprocess.check_output([str(reader), '--coff-imports', str(file)], text=True)
        for name in re.findall(r'^\s+Name: (.+\.dll)\s*$', text, re.MULTILINE | re.IGNORECASE):
            lower = name.lower()
            if lower in SYSTEM_DLLS or lower.startswith(('api-ms-win-', 'ext-ms-win-')) or lower in seen:
                continue
            source = next((folder / name for folder in (kit / 'bin', kit / 'deps/bin') if (folder / name).is_file()), None)
            if source is None:
                raise ValueError('Missing redistributable DLL: ' + name)
            seen.add(lower)
            target = tools / name
            shutil.copyfile(source, target)
            pending.append(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='NEW output directory')
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--embed-toolchain', action='store_true')
    parser.add_argument('--wheelhouse', type=Path, help='Compatible Windows x64 wheels for offline preparation')
    parser.add_argument('--menu-glyphs', type=Path, help='Authored PNG glyph master for remastered menus')
    parser.add_argument('--version', default='0.1.0-preview.3')
    parser.add_argument('--iscc', type=Path)
    parser.add_argument('--zip', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9][A-Za-z0-9.-]*', args.version):
        parser.error('invalid version')
    output, kit = args.output.resolve(), args.toolchain.resolve()
    if output.exists():
        parser.error('output must be a NEW directory')
    if not (kit / 'bin/clang++.exe').is_file():
        parser.error('select the complete Windows cmake-clang-v1 kit')
    if args.menu_glyphs is not None and not args.menu_glyphs.is_file():
        parser.error('select the authored menu glyph master')
    stage = output / 'app'
    stage.mkdir(parents=True)
    stage_sdk(stage, args.menu_glyphs)
    shutil.copyfile(Path(__file__).with_name('player_setup.py'), stage / 'player_setup.py')
    binary = stage / 'DukeTTK-PTBR.exe'
    subprocess.run([str(kit / 'bin/clang++.exe'), '-std=c++17', '-O2', '-static', '-municode', '-mwindows',
                    str(Path(__file__).with_name('player_assistant.cpp')), '-o', str(binary),
                    '-lcomdlg32', '-lshell32', '-lole32', '-lopengl32', '-lgdi32'], check=True)
    tools = stage / 'bin'
    tools.mkdir()
    for name, folder in [('psxrecomp-game', 'build-recompiler'), ('psxrecomp-bios', 'build-recompiler'), ('sector_check', 'build-tools')]:
        shutil.copyfile(ROOT / folder / (name + '.exe'), tools / (name + '.exe'))
    bundle_dlls(tools, kit)
    if args.embed_toolchain:
        shutil.copytree(kit, stage / 'toolchain', symlinks=False,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if args.wheelhouse:
        wheels = list(args.wheelhouse.resolve().glob('*.whl'))
        if not wheels:
            parser.error('wheelhouse must contain compatible .whl packages')
        (stage / 'wheels').mkdir()
        for wheel in wheels:
            shutil.copyfile(wheel, stage / 'wheels' / wheel.name)
    shutil.copyfile(GAME / 'LICENSE', stage / 'LICENSE')
    shutil.copyfile(ROOT / 'psxrecomp/THIRD_PARTY_ATTRIBUTION.md', stage / 'THIRD_PARTY_ATTRIBUTION.md')
    shutil.copyfile(kit / 'LICENSE.TXT', stage / 'TOOLCHAIN-LICENSE.txt')
    guide = GAME / 'documentation/instalacao-windows-ptbr.md'
    if guide.is_file():
        shutil.copyfile(guide, stage / 'LEIA-ME.md')
    (stage / 'VERSION').write_text(args.version + '\n', encoding='ascii')
    print('Player stage: ' + str(stage), flush=True)
    if args.zip:
        target = output / f'DukeTTK-PTBR-{args.version}-Windows.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for file in stage.rglob('*'):
                if file.is_file():
                    archive.write(file, Path('DukeTTK-PTBR') / file.relative_to(stage))
        print('Portable ZIP: ' + str(target), flush=True)
    if args.iscc:
        subprocess.run([str(args.iscc.resolve()), '/DStageDir=' + str(stage), '/DReleaseVersion=' + args.version,
                        str(Path(__file__).with_name('windows.iss'))], check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
