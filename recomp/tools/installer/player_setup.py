"""Player-side preparation. Uses a private project and the player's own disc.

The native assistant runs this with the portable kit's Python. No Git checkout
or globally installed build tools are needed on the player's machine.
"""
import argparse
import hashlib
import importlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

MIN_FREE = 8 * 1024**3
MODULES = {'numpy': 'numpy', 'Pillow': 'PIL.Image', 'capstone': 'capstone'}
LIBRARY_CHECKS = {'Biblioteca ' + name for name in MODULES}

class DiscSelectionError(ValueError):
    pass


def contained(root, relative):
    p = PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative or ':' in relative:
        raise ValueError('Caminho inválido no pacote de instalação.')
    target = (root / Path(*p.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Caminho fora da pasta de preparação.')
    return target


def version(text):
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', text)
    return tuple(int(x or 0) for x in match.groups()) if match else (0, 0, 0)


def command_version(path):
    try:
        result = subprocess.run([str(path), '--version'], capture_output=True, text=True,
                                timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return result.returncode == 0, result.stdout.splitlines()[0] if result.stdout else ''
    except (OSError, subprocess.SubprocessError):
        return False, ''


def requirements(app, kit, data):
    checks = []
    def add(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))
    add('Python 3.11 ou superior (64 bits)', sys.version_info >= (3, 11) and sys.maxsize > 2**32,
        'Use o Python de 64 bits incluído no kit portátil.')
    for name, module in MODULES.items():
        try:
            importlib.import_module(module)
            good = True
        except Exception:
            good = False
        add('Biblioteca ' + name, good,
            'O assistente instala os componentes incluídos no pacote completo.')
    for binary, minimum in [('cmake', (3, 20, 0)), ('ninja', (1, 10, 0)), ('clang++', (16, 0, 0))]:
        ok, text = command_version(kit / 'bin' / (binary + '.exe'))
        add(binary, ok and version(text) >= minimum, text or 'Reinstale usando o instalador completo.')
    for name, path in [('SDL3', 'deps/include/SDL3/SDL.h'), ('zlib', 'deps/include/zlib.h')]:
        add(name, (kit / path).is_file(), 'Incluído no kit portátil. Não exige instalação separada.')
    add('Pacote do aplicativo', (app / 'sdk/sdk-manifest.json').is_file()
        and (app / 'sdk/tools/local/run.py').is_file(), 'Extraia ou reinstale o pacote completo do aplicativo.')
    for name in ('psxrecomp-game', 'psxrecomp-bios', 'sector_check'):
        add(name, (app / 'bin' / (name + '.exe')).is_file(), 'Ferramenta interna ausente. Reinstale o aplicativo.')
    data.mkdir(parents=True, exist_ok=True)
    add('8 GB livres para a primeira preparação', shutil.disk_usage(data).free >= MIN_FREE,
        'Libere espaço na unidade dos dados do aplicativo. Esta é uma reserva de preparação, não um teste de FPS.')
    try:
        with tempfile.TemporaryFile(dir=data):
            pass
        writable = True
    except OSError:
        writable = False
    add('Pasta de dados gravável', writable, 'Use uma pasta do seu usuário, fora de Program Files.')
    return checks


def save_report(checks, data):
    data.mkdir(parents=True, exist_ok=True)
    result = dict(ready=all(x['ok'] for x in checks), checks=checks)
    (data / 'requirements.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    text = '\n\n'.join(('OK - ' if x['ok'] else 'FALTA - ') + x['name']
                       + ('' if x['ok'] else '\n' + x['detail']) for x in checks)
    (data / 'requirements.txt').write_text(text, encoding='utf-8')
    return result['ready']


def check_status(app, kit, data):
    checks = requirements(app, kit, data)
    if save_report(checks, data):
        return 0
    missing = {check['name'] for check in checks if not check['ok']}
    if missing <= LIBRARY_CHECKS and any((app / 'wheels').glob('*.whl')):
        return 3
    if '8 GB livres para a primeira preparação' in missing:
        message = 'Libere pelo menos 8 GB na unidade onde o jogo guarda os dados e tente novamente.'
    elif 'Pasta de dados gravável' in missing:
        message = 'O assistente não consegue gravar na pasta de dados. Confira as permissões e tente novamente.'
    else:
        message = 'Faltam componentes do jogo. Execute novamente o instalador completo.'
    (data / 'last-error.txt').write_text(message, encoding='utf-8')
    return 2


def run(command, cwd, env, status_file=None):
    print('Etapa: ' + Path(str(command[0])).name + ' ' + ' '.join(map(str, command[1:3])), flush=True)
    if status_file is None:
        subprocess.run(list(map(str, command)), cwd=cwd, env=env, check=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return
    with subprocess.Popen(list(map(str, command)), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
        for line in process.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            progress = re.match(rb'^\[(\d+)/(\d+)\] (?!Re-checking globbed directories)', line) if status_file else None
            if progress:
                done, total = map(int, progress.groups())
                if 0 < done <= total:
                    status_file.write_text(f'{done} {total}\nRecompilando o jogo.\n'
                                           'Algumas etapas levam mais tempo. Mantenha esta janela aberta.',
                                           encoding='utf-8')
        status = process.wait()
        if status:
            raise subprocess.CalledProcessError(status, list(map(str, command)))


def copy_sdk(app, project):
    source = app / 'sdk'
    raw = (source / 'sdk-manifest.json').read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get('schema') != 1 or not isinstance(manifest.get('files'), list) or not manifest['files']:
        raise ValueError('Versão do pacote de instalação não reconhecida.')
    names = set()
    for entry in manifest['files']:
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) or not isinstance(entry.get('sha256'), str):
            raise ValueError('Manifesto de instalação inválido.')
        name = entry['path'].casefold()
        if not name or name in names:
            raise ValueError('Caminho duplicado ou vazio no pacote.')
        names.add(name)
    # Verify the complete source payload before modifying the private project.
    for entry in manifest['files']:
        src = contained(source, entry['path'])
        with src.open('rb') as payload:
            digest = hashlib.file_digest(payload, 'sha256').hexdigest()
        if digest != entry['sha256']:
            raise ValueError('Pacote incompleto ou alterado: ' + entry['path'])
        contained(project, entry['path'])
    for entry in manifest['files']:
        src, dst = contained(source, entry['path']), contained(project, entry['path'])
        # Retrying preparation should preserve valid build inputs and their
        # timestamps, so Ninja can resume instead of rebuilding everything.
        if dst.is_file():
            with dst.open('rb') as payload:
                if hashlib.file_digest(payload, 'sha256').hexdigest() == entry['sha256']:
                    continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return hashlib.sha256(raw).hexdigest()


def prepare(app, kit, data, image, jobs):
    # Title tools resolve their workspace as recomp/../; preserve that layout.
    project = data / 'project/recomp'
    incoming = image or project / 'disc/time-to-kill.cue'
    if not incoming.is_file():
        raise DiscSelectionError('Selecione a cópia original USA do jogo para continuar.')
    sys.path.insert(0, str(app / 'sdk/tools/local'))
    import disc_lab
    print('Validando sua cópia USA SLUS-00583. O arquivo original não será modificado.', flush=True)
    # Publish the prepared copy only when the entire import completed. A cancel
    # during copying must not leave a partial image mistaken for a user file.
    (data / 'status.txt').write_text('Conferindo se o disco é da edição USA…', encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='disc-import-', dir=data) as staging:
        temporary = Path(staging)
        try:
            disc_lab.import_disc(incoming, temporary, app / 'bin/sector_check.exe')
        except (ValueError, OSError, subprocess.CalledProcessError) as error:
            print('Disco recusado: ' + str(error), flush=True)
            raise DiscSelectionError('Este disco é incompatível ou está incompleto. Escolha o .cue da edição USA (SLUS-00583) '
                                     'e mantenha o .bin na mesma pasta. Você também pode escolher o .bin original.') from error
        # An invalid replacement disc should leave an existing install playable.
        (data / 'ready.json').unlink(missing_ok=True)
        (data / 'status.txt').write_text('Conferindo os arquivos do aplicativo...', encoding='utf-8')
        fingerprint = copy_sdk(app, project)
        destination = project / 'disc'
        destination.mkdir(exist_ok=True)
        for file in temporary.iterdir():
            if file.is_file():
                os.replace(file, destination / file.name)
    env = dict(os.environ)
    env.update(PATH=str(Path(sys.executable).parent) + os.pathsep + str(kit / 'bin') + os.pathsep + env.get('PATH', ''),
               CC=str(kit / 'bin/clang.exe'), CXX=str(kit / 'bin/clang++.exe'),
               RETCOMM_TOOLCHAIN_DIR=str(kit), PSXRECOMP_TOOLCHAIN_DIR=str(kit),
               ZLIB_ROOT=str(kit / 'deps'), SDL3_DIR=str(kit / 'deps/lib/cmake/SDL3'),
               PSXRECOMP_GAME=str(app / 'bin/psxrecomp-game.exe'),
               PSXRECOMP_BIOS=str(app / 'bin/psxrecomp-bios.exe'))
    if sys.prefix != sys.base_prefix:
        env['VIRTUAL_ENV'] = sys.prefix
    (data / 'status.txt').write_text('Preparando o código a partir do seu disco...', encoding='utf-8')
    run([sys.executable, project / 'psxrecomp/psxrecomp_cli.py', 'generate', '--config', 'game.local.toml',
         '--project-root', project, '--disc', 'disc/time-to-kill.cue'], project, env)
    (data / 'status.txt').write_text('Configurando o aplicativo para este computador...', encoding='utf-8')
    # CMake 3.30+ can populate the vendored archive directly. Avoid the
    # nested Ninja build, whose cached manifest can go stale on an upgrade.
    configure = [kit / 'bin/cmake.exe', '--preset', 'local-dev', '-DCMAKE_BUILD_TYPE=Release',
         '-DPSX_DEPS_OFFLINE=ON', '-DCMAKE_POLICY_DEFAULT_CMP0168=NEW',
         '-DCMAKE_C_COMPILER_LAUNCHER=', '-DCMAKE_CXX_COMPILER_LAUNCHER=',
         '-DCMAKE_C_COMPILER=' + env['CC'], '-DCMAKE_CXX_COMPILER=' + env['CXX'],
         '-DPython3_EXECUTABLE=' + sys.executable]
    # Changing the bundled compiler on upgrade can make CMake discard the
    # cache and rerun without the remaining command-line settings. Reapply
    # the private interpreter after that compiler transition has settled.
    run(configure, project, env)
    run(configure, project, env)
    (data / 'status.txt').write_text('Iniciando a recompilação. Algumas etapas podem levar vários minutos.', encoding='utf-8')
    run([kit / 'bin/cmake.exe', '--build', '--preset', 'local-dev', '--parallel', jobs], project,
        dict(env, NINJA_STATUS='[%f/%t] '),
        status_file=data / 'status.txt')
    (data / 'status.txt').write_text('Recompilação concluída. Finalizando os arquivos do jogo...', encoding='utf-8')
    # Overlay builders use this conventional emitter location; copy only the
    # redistributable emitter, never a generated game DLL from another machine.
    emitter = project / 'build-recompiler/psxrecomp-game.exe'
    emitter.parent.mkdir(parents=True, exist_ok=True)
    for file in (app / 'bin').iterdir():
        if file.is_file():
            shutil.copyfile(file, emitter.parent / file.name)
    run([sys.executable, project / 'tools/local/build_movie_overlay.py', '--jobs', jobs], project, env)
    run([sys.executable, project / 'tools/local/build_math_overlay.py', '--if-ready'], project, env)
    art = project / 'assets/remastered-art.zip'
    if (app / 'sdk/assets/remastered-art.zip').is_file():
        (data / 'status.txt').write_text('Preparando as texturas remasterizadas da campanha...', encoding='utf-8')
        run([sys.executable, project / 'tools/local/prepare_installed_art.py', art], project, env)
    glyphs = project / 'assets/ui/installer-menu-glyphs.png'
    if (app / 'sdk/assets/ui/installer-menu-glyphs.png').is_file():
        (data / 'status.txt').write_text('Preparando as letras e a interface remasterizadas...', encoding='utf-8')
        ui = project / 'analysis/campaign-art/ui'
        has_hud = all((ui / name).is_file() for name in
                      ('inventory-master.png', 'mission-cutout.png', 'hud-materials.png'))
        if has_hud:
            run([sys.executable, project / 'tools/local/build_campaign_inventory_icons.py'], project, env)
            run([sys.executable, project / 'tools/local/build_campaign_hud.py'], project, env)
            run([sys.executable, project / 'tools/local/build_campaign_glyphs.py', '--master', glyphs, '--font-only'], project, env)
        menu = [sys.executable, project / 'tools/local/build_campaign_menu_font.py', '--master', glyphs]
        if has_hud:
            menu.append('--with-hud')
        run(menu, project, env)
    ready = data / 'ready.json'
    temporary = ready.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(schema=1, sdk=fingerprint)), encoding='utf-8')
    temporary.replace(ready)
    (data / 'prepared-version.txt').write_text((app / 'VERSION').read_text(encoding='ascii'), encoding='ascii')
    print('Preparação concluída. O jogo está pronto.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('check', 'install-libraries', 'prepare', 'play'))
    parser.add_argument('--app-root', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    app, kit, data = args.app_root.resolve(), args.toolchain.resolve(), args.data_dir.resolve()
    if not 1 <= args.jobs <= 16:
        parser.error('jobs must be 1..16')
    data.mkdir(parents=True, exist_ok=True)
    try:
        if args.operation == 'check':
            return check_status(app, kit, data)
        if args.operation == 'install-libraries':
            # Install into an application-private environment, never the user's Python.
            import venv
            target = data / 'python'
            venv.EnvBuilder(with_pip=True).create(target)
            python = target / 'Scripts/python.exe'
            command = [python, '-m', 'pip', 'install', '--only-binary=:all:',
                       '-r', app / 'sdk/requirements-local.txt', '--no-index', '--find-links', app / 'wheels']
            run(command, app, os.environ.copy())
            (data / 'python-kit.txt').write_text(str(kit), encoding='utf-8')
            return 0
        if args.operation == 'prepare':
            if not save_report(requirements(app, kit, data), data):
                raise ValueError('Faltam componentes para preparar o jogo. Abra os detalhes para ver o que precisa corrigir.')
            prepare(app, kit, data, args.image.resolve() if args.image else None, args.jobs)
            return 0
        project = data / 'project/recomp'
        ready = json.loads((data / 'ready.json').read_text())
        fingerprint = hashlib.sha256((app / 'sdk/sdk-manifest.json').read_bytes()).hexdigest()
        if ready.get('sdk') != fingerprint:
            raise ValueError('O aplicativo foi atualizado. Clique em Preparar para atualizar os arquivos locais.')
        env = dict(os.environ, DNTTK_LANGUAGE='pt-BR',
                   RETCOMM_TOOLCHAIN_DIR=str(kit), PSXRECOMP_TOOLCHAIN_DIR=str(kit))
        env['PATH'] = str(kit / 'bin') + os.pathsep + env.get('PATH', '')
        env.pop('DNTTK_TEST_INPUT', None)
        env.pop('DNTTK_TEST_UNCAPTURED', None)
        env.pop('DNTTK_TEST_EDGES', None)
        settings = data / 'config/player-profiles.json'
        command = [sys.executable, project / 'tools/local/run.py', '--settings-file', settings,
                   '--memcard-dir', data / 'saves']
        ui = project / 'analysis/campaign-art/ui'
        if (ui / 'menu-font/with-hud.ttkpack').is_file():
            command += ['--hud-hd']
        elif (app / 'sdk/assets/ui/installer-menu-glyphs.png').is_file():
            command += ['--menu-hd']
        preset = settings.with_name('full-hd-preset-v1')
        if not preset.is_file():
            defaults = ['--renderer', 'opengl', '--internal-scale', '2', '--frame-rate', 'auto',
                        '--world-renderer', 'polymorph', '--geometry-precision', 'corrected',
                        '--texture-precision', 'corrected', '--antialias', 'smooth',
                        '--display', 'borderless', '--window-width', '1920', '--widescreen', '16:9',
                        '--vsync', 'on', '--output-filter', 'linear']
            if not settings.is_file() and (project / 'analysis/installed-art/00/pack.ttkpack').is_file():
                defaults += ['--texture-set', 'realistic']
            run(command + defaults + ['--show-settings'], project, env)
            preset.parent.mkdir(parents=True, exist_ok=True)
            preset.touch()
        run(command, project, env)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('Não foi possível continuar: ' + str(error), flush=True)
        message = ('Uma ferramenta de preparação não concluiu a etapa. Abra Ver detalhes para consultar '
                   'o motivo e tente novamente após corrigir o problema.' if isinstance(error, subprocess.SubprocessError)
                   else 'Não foi possível continuar: ' + str(error))
        (data / 'last-error.txt').write_text(message, encoding='utf-8')
        return 4 if isinstance(error, DiscSelectionError) else 1


if __name__ == '__main__':
    raise SystemExit(main())
