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
            'Clique em Instalar bibliotecas e depois em Verificar novamente.')
    for binary, minimum in [('cmake', (3, 20, 0)), ('ninja', (1, 10, 0)), ('clang++', (16, 0, 0))]:
        ok, text = command_version(kit / 'bin' / (binary + '.exe'))
        add(binary, ok and version(text) >= minimum, text or 'Selecione o kit cmake-clang-v1 completo.')
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
    return 2


def run(command, cwd, env, status_file=None):
    print('Etapa: ' + Path(str(command[0])).name + ' ' + ' '.join(map(str, command[1:3])), flush=True)
    with subprocess.Popen(list(map(str, command)), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
        for line in process.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            progress = re.match(rb'^\[(\d+)/(\d+)\]', line) if status_file else None
            if progress:
                status_file.write_text('Preparando o aplicativo: ' + progress[1].decode() + ' de '
                                       + progress[2].decode() + ' etapas concluídas.\n'
                                       'A primeira preparação pode levar vários minutos. Aguarde.', encoding='utf-8')
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
        if hashlib.sha256(src.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Pacote incompleto ou alterado: ' + entry['path'])
        contained(project, entry['path'])
    for entry in manifest['files']:
        src, dst = contained(source, entry['path']), contained(project, entry['path'])
        # Retrying preparation should preserve valid build inputs and their
        # timestamps, so Ninja can resume instead of rebuilding everything.
        if dst.is_file() and hashlib.sha256(dst.read_bytes()).hexdigest() == entry['sha256']:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return hashlib.sha256(raw).hexdigest()


def prepare(app, kit, data, image, jobs):
    # Title tools resolve their workspace as recomp/../; preserve that layout.
    project = data / 'project/recomp'
    project.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(app / 'sdk/tools/local'))
    import disc_lab
    incoming = image or project / 'disc/time-to-kill.cue'
    print('Validando sua cópia USA SLUS-00583. O arquivo original não será modificado.', flush=True)
    # Publish the prepared copy only when the entire import completed. A cancel
    # during copying must not leave a partial image mistaken for a user file.
    (data / 'status.txt').write_text('Validando e preparando sua cópia USA. O original será preservado.', encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='disc-import-', dir=data) as staging:
        temporary = Path(staging)
        try:
            disc_lab.import_disc(incoming, temporary, app / 'bin/sector_check.exe')
        except (ValueError, OSError) as error:
            raise ValueError('Não foi possível validar o disco. Selecione um dump USA SLUS-00583 compatível, '
                             'em CUE+BIN ou IMG MODE2/2352. Detalhes: ' + str(error)) from error
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
    env.update(PATH=str(kit / 'bin') + os.pathsep + env.get('PATH', ''),
               CC=str(kit / 'bin/clang.exe'), CXX=str(kit / 'bin/clang++.exe'),
               RETCOMM_TOOLCHAIN_DIR=str(kit), PSXRECOMP_TOOLCHAIN_DIR=str(kit),
               ZLIB_ROOT=str(kit / 'deps'), SDL3_DIR=str(kit / 'deps/lib/cmake/SDL3'),
               PSXRECOMP_GAME=str(app / 'bin/psxrecomp-game.exe'),
               PSXRECOMP_BIOS=str(app / 'bin/psxrecomp-bios.exe'))
    (data / 'status.txt').write_text('Preparando o código a partir do seu disco...', encoding='utf-8')
    run([sys.executable, project / 'psxrecomp/psxrecomp_cli.py', 'generate', '--config', 'game.local.toml',
         '--project-root', project, '--disc', 'disc/time-to-kill.cue'], project, env)
    (data / 'status.txt').write_text('Configurando o aplicativo para este computador...', encoding='utf-8')
    run([kit / 'bin/cmake.exe', '--preset', 'local-dev', '-DCMAKE_BUILD_TYPE=Release',
         '-DPSX_DEPS_OFFLINE=ON',
         '-DCMAKE_C_COMPILER_LAUNCHER=', '-DCMAKE_CXX_COMPILER_LAUNCHER=',
         '-DCMAKE_C_COMPILER=' + env['CC'], '-DCMAKE_CXX_COMPILER=' + env['CXX'],
         '-DPython3_EXECUTABLE=' + sys.executable], project, env)
    (data / 'status.txt').write_text('Preparando o aplicativo. A primeira vez pode levar vários minutos.\nO registro detalhado pode ser aberto pelo botão Ver registro.', encoding='utf-8')
    run([kit / 'bin/cmake.exe', '--build', '--preset', 'local-dev', '--parallel', jobs], project, env,
        status_file=data / 'status.txt')
    # Overlay builders use this conventional emitter location; copy only the
    # redistributable emitter, never a generated game DLL from another machine.
    emitter = project / 'build-recompiler/psxrecomp-game.exe'
    emitter.parent.mkdir(parents=True, exist_ok=True)
    for file in (app / 'bin').iterdir():
        if file.is_file():
            shutil.copyfile(file, emitter.parent / file.name)
    (data / 'status.txt').write_text('Concluindo a preparação dos vídeos e das melhorias...', encoding='utf-8')
    run([sys.executable, project / 'tools/local/build_movie_overlay.py', '--jobs', jobs], project, env)
    run([sys.executable, project / 'tools/local/build_math_overlay.py', '--if-ready'], project, env)
    glyphs = project / 'assets/ui/installer-menu-glyphs.png'
    if (app / 'sdk/assets/ui/installer-menu-glyphs.png').is_file():
        (data / 'status.txt').write_text('Preparando a tipografia remasterizada dos menus...', encoding='utf-8')
        run([sys.executable, project / 'tools/local/build_campaign_menu_font.py', '--master', glyphs], project, env)
    ready = data / 'ready.json'
    temporary = ready.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(schema=1, sdk=fingerprint)), encoding='utf-8')
    temporary.replace(ready)
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
            (data / 'python-kit.txt').write_text(str(kit), encoding='utf-8')
            python = target / 'Scripts/python.exe'
            command = [python, '-m', 'pip', 'install', '--only-binary=:all:',
                       '-r', app / 'sdk/requirements-local.txt']
            if (app / 'wheels').is_dir():
                command += ['--no-index', '--find-links', app / 'wheels']
            run(command, app, os.environ.copy())
            return 0
        if args.operation == 'prepare':
            if not save_report(requirements(app, kit, data), data):
                raise ValueError('Há requisitos pendentes. Verifique a lista antes de continuar.')
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
        if (app / 'sdk/assets/ui/installer-menu-glyphs.png').is_file():
            command += ['--menu-hd']
        if not settings.is_file():
            command += ['--renderer', 'opengl', '--internal-scale', '2', '--frame-rate', 'auto',
                        '--world-renderer', 'polymorph', '--geometry-precision', 'corrected',
                        '--texture-precision', 'corrected']
        run(command, project, env)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('Não foi possível continuar: ' + str(error), flush=True)
        message = ('Uma ferramenta de preparação não concluiu a etapa. Abra Ver registro para consultar '
                   'o motivo e tente novamente após corrigir o problema.' if isinstance(error, subprocess.SubprocessError)
                   else 'Não foi possível continuar: ' + str(error))
        (data / 'last-error.txt').write_text(message, encoding='utf-8')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
