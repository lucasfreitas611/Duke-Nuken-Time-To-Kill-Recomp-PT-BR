# Duke Nukem: Time to Kill Recomp - Português do Brasil

Recompilação nativa de Duke Nukem: Time to Kill para PC, com interface em português do Brasil, controles modernizados de teclado e mouse e ajustes de compilação para Windows com Clang/LLVM-MinGW.

Este projeto deriva de [MusicMonsterMod/duke-nukem-time-to-kill-recomp](https://github.com/MusicMonsterMod/duke-nukem-time-to-kill-recomp). O histórico, a implementação e a documentação desse projeto foram preservados. A base desta versão é o commit `95a5471`. Esta não é uma tradução oficial dos detentores dos direitos do jogo.

**É necessário possuir uma cópia original USA, SLUS-00583.** Não são distribuídos disco, BIOS comercial, código gerado do jogo, executável do jogo já recompilado, fontes extraídas, saves ou cartões de memória. A edição europeia/PAL não é compatível com este build.

## Instalação assistida no Windows

Baixe o Setup para Windows 10/11 x64. O assistente verifica os requisitos e
prepara o jogo quando você seleciona a imagem da sua cópia original USA.
O pacote completo inclui as ferramentas e bibliotecas para a preparação offline.

- [Instalador nos Releases](https://github.com/lucasfreitas611/Duke-Nuken-Time-To-Kill-Recomp-PT-BR/releases)
- [Tutorial de instalação, atualização e requisitos](documentation/instalacao-windows-ptbr.md)

## O que foi acrescentado

- Cerca de 500 entradas de tradução: menus, configurações, ações dos controles, objetivos da campanha, itens e mensagens de salvar/carregar.
- Composição de acentos e cedilha usando as fontes do jogo, sem alterar a imagem original do disco ou o formato dos pacotes de fontes.
- Tradução apenas na apresentação. Chaves de configuração, comandos, atalhos e dados persistentes mantêm os identificadores originais.
- Interface em inglês disponível com `DNTTK_LANGUAGE=en`.
- Correção da declaração `dllexport` ao compilar os módulos de vídeo/geometria com Clang no Windows. A correção integra o patch de framework aplicado pelo build.
- Otimização desativada apenas no arquivo gerado `SLUS_005.83_full_65.c`, no Windows com Clang, para evitar a demora excessiva de compilação dessa função. Os demais arquivos mantêm a otimização original. Essa exceção pode afetar o desempenho das rotinas desse bloco.
- Arquivos `.cmd` para abrir os modos em português, inglês e Vanilla, e testes nativos da localização.
- Correções de precisão de vértices e texturas e ajustes de profundidade no modo Modernizado com OpenGL.
- VSync, opções de apresentação e ferramentas locais para testar a HUD HD e as texturas da campanha.
- Atlas HD mais compacto, recuperação de cadência e redução de quadros repetidos durante movimentação e combate.
- Instalador offline com verificação de requisitos, importação do disco USA e tipografia remasterizada dos menus.

As falas e os vídeos continuam no idioma original. Textos incorporados em imagens, nomes próprios e interfaces de diagnóstico podem permanecer em inglês. O catálogo cobre os objetivos da campanha, mas a campanha completa ainda não foi revisada visualmente em português.

## Baixar o código completo

Use Git com os submódulos. O download ZIP não preenche essas dependências.

```powershell
git clone --recurse-submodules https://github.com/lucasfreitas611/Duke-Nuken-Time-To-Kill-Recomp-PT-BR.git
cd Duke-Nuken-Time-To-Kill-Recomp-PT-BR
```

Em uma cópia já existente, execute `git submodule update --init --recursive`.
Coloque seu `.bin` e `.cue` em `game/`. O `.cue` deve apontar para o nome correto do `.bin`. Os originais são lidos para preparar uma cópia local em `recomp/disc/`.

## Compilar no Windows

Pré-requisitos: Python 3.11 ou superior, Git, CMake 3.20 ou superior, Ninja e um compilador C/C++ x64 compatível com MinGW. Esta versão foi compilada com o pacote portátil `cmake-clang-v1` do ecossistema PSXRecomp/RetComM (Clang/LLVM-MinGW, CMake, Ninja, SDL3 e zlib). Não misture um diretório de build configurado para MSVC com ferramentas MinGW.

Se estiver usando esse pacote portátil, prepare a sessão do PowerShell abaixo. Substitua o caminho de exemplo pela pasta do seu pacote:

```powershell
$toolchain = 'C:\caminho\para\cmake-clang-v1'
$env:RETCOMM_TOOLCHAIN_DIR = $toolchain
$env:Path = "$toolchain\bin;" + $env:Path
$env:CC = "$toolchain\bin\clang.exe"
$env:CXX = "$toolchain\bin\clang++.exe"
$env:ZLIB_ROOT = "$toolchain\deps"
$env:SDL3_DIR = "$toolchain\deps\lib\cmake\SDL3"
```

Na raiz do repositório, com seu disco em `game/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r recomp/requirements-local.txt
.\.venv\Scripts\python.exe recomp/tools/local/build.py --jobs 4
```

O processo aplica os patches, valida o disco, gera o código do jogo e do OpenBIOS, prepara os recursos e compila o executável. Não é necessário fornecer um BIOS comercial para o caminho OpenBIOS usado neste build.

Se o CMake selecionar um Python diferente do ambiente virtual, execute na pasta `recomp/`, após a geração inicial:

```powershell
$pythonBuild = (Resolve-Path '..\.venv\Scripts\python.exe').Path
cmake --preset local-dev "-DPython3_EXECUTABLE=$pythonBuild"
cmake --build --preset local-dev --parallel 4
```

Se o `ccache` impedir o início da compilação no seu ambiente, desative somente esse cache na configuração local, também em `recomp/`:

```powershell
cmake --preset local-dev '-DCMAKE_C_COMPILER_LAUNCHER=' '-DCMAKE_CXX_COMPILER_LAUNCHER='
cmake --build --preset local-dev --parallel 4
```

Mantenha `recomp/build-local/cache/`, os pacotes de recursos e os demais arquivos gerados junto do executável. Eles não são distribuídos neste repositório.

## Jogar

Depois de compilar, abra um destes arquivos na raiz do repositório:

| Arquivo | Modo |
| --- | --- |
| `Jogar Duke TTK.cmd` | Modernizado, interface PT-BR |
| `Jogar Duke TTK em Ingles.cmd` | Modernizado, interface em inglês |
| `Jogar Duke TTK Original.cmd` | Vanilla, comportamento original |

Os arquivos procuram o Python de `.venv/`, o ambiente virtual na pasta superior quando presente e, por último, o Python do PATH. Para usar outro local de toolchain, defina `RETCOMM_TOOLCHAIN_DIR`.

Também é possível iniciar pelo launcher Python:

```powershell
.\.venv\Scripts\python.exe recomp/tools/local/run.py
```

WASD movimenta; o mouse controla a câmera; o botão esquerdo atira; Espaço pula; E interage; Ctrl agacha; Esc pausa. Enter e as setas navegam pelos menus, F11 alterna a tela cheia e P alterna a perspectiva nas situações suportadas. Clique na janela para dar foco; retomar pelo menu de pausa recaptura o mouse durante a partida.

Saves e preferências ficam nas pastas locais ignoradas pelo Git. Use o launcher: abrir o executável diretamente não configura todos os recursos modernizados.

## Validação desta versão

Em Windows, foram verificados: compilação do executável e dos módulos de vídeo e geometria; inicialização com OpenGL; tela de título e menus; tradução visível no menu principal e na tela de vídeo. Os testes nativos de localização verificam tradução, retorno ao inglês, composição dos acentos e quebra de linha. Isso não equivale à validação de toda a campanha, todos os controles ou todas as telas. O projeto original tem Linux como plataforma validada.

Para executar os testes de localização após preparar o disco e os recursos:

```powershell
cmake --build recomp/build-local --target ttk-pt-br-test --parallel 4
.\recomp\build-local\ttk-pt-br-test.exe .\recomp\build-local\ttk-fonts.pack
```

## Documentação e próximos ajustes

- [README original, preservado](README_UPSTREAM.md)
- [Índice da documentação técnica original](documentation/README.md)
- [Manual de controles e recursos original](GAME_MANUAL.md)
- [Instruções originais de build](documentation/04-build-and-run.md)
- [Estado documentado do projeto original](documentation/00-status.md)
- [Histórico de tarefas e melhorias original](MODERNIZATION_JOBS.md)
- [Catálogo PT-BR](recomp/src/ttk/pt_br.inc)
- [Localização e composição dos caracteres](recomp/src/ttk/localization.h)

Os documentos originais registram o trabalho e os testes do autor original; não representam testes adicionais realizados neste fork. Os ajustes locais do framework ficam em `recomp/patches/time-to-kill-accepted-source.patch`. Os submódulos continuam nas revisões públicas fixadas pelo projeto.

## Créditos e licenças

Implementação e modernização originais por MusicMonsterMod, sobre PSXRecomp, os forks e as bibliotecas identificados no [README original](README_UPSTREAM.md). Os créditos, avisos e licenças foram preservados. A licença MIT da raiz não substitui as licenças do framework, das bibliotecas ou do jogo. Os direitos do jogo e dos seus dados continuam com os respectivos titulares.
