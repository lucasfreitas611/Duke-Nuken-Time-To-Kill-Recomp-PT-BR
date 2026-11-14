# Instalação assistida no Windows

O assistente `DukeTTK-PTBR.exe` prepara o jogo usando a cópia original do
jogador. O pacote contém ferramentas e código do projeto; o executável do jogo
e os recursos extraídos são gerados no computador do jogador. Não exige clonar
o GitHub, instalar Git ou executar comandos de compilação manualmente.

Na página de Releases, abra **Assets** e baixe
`DukeTTK-PTBR-0.1.0-preview.3-Setup.exe`.
[Releases do projeto](https://github.com/lucasfreitas611/Duke-Nuken-Time-To-Kill-Recomp-PT-BR/releases)

## Requisitos verificados

| Requisito | Como resolver se faltar |
| --- | --- |
| Windows 10/11 x64, processador AMD64 | Usar Windows x64. Este pacote não oferece suporte a Windows 32 bits ou ARM. |
| OpenGL 3.3 ou superior | Atualizar o driver pelo site oficial do fabricante da GPU e verificar novamente. Não baixar DLLs avulsas. |
| Kit portátil `cmake-clang-v1` para Windows x64 | Se o pacote não incluir o kit, clicar em Baixar kit, extrair o arquivo correto e selecionar a pasta que contém `bin`, `deps` e `python`. |
| Python 3.11+ x64, CMake 3.20+, Ninja 1.10+, Clang 16+, SDL3 e zlib | Usar o kit completo. O assistente verifica versões das ferramentas e a presença dos componentes. |
| numpy, Pillow e capstone | O pacote completo instala as bibliotecas incluídas automaticamente. No pacote reduzido, clique em Instalar bibliotecas. O assistente usa um ambiente privado. |
| Pasta de dados gravável e 8 GB livres | Liberar espaço na unidade dos dados. A reserva é para a primeira preparação, não uma medição de desempenho. |
| Disco USA SLUS-00583 compatível | Selecionar o CUE ou BIN/IMG da própria cópia original. O conteúdo e a integridade dos setores são validados antes da geração. |

O teste de OpenGL consulta o driver de verdade. A lista de requisitos não
garante um FPS específico: desempenho depende de CPU, GPU, resolução e fase.
O fluxo usa o kit MinGW/Clang; não exige Visual Studio nem um Visual C++
Redistributable instalado separadamente.

Kit oficial: [RetComM Toolchains](https://github.com/TechnicallyComputers/retcomm-toolchains/releases).
Para bibliotecas ausentes, é necessário acesso à internet ao
[PyPI](https://pypi.org/), salvo quando o mantenedor incluir wheels compatíveis
na pasta `wheels` do pacote. O instalador não baixa um disco do jogo.

## Para jogar

1. Execute o Setup e mantenha marcada a opção de abrir o assistente.
   A instalação é por usuário.
2. Aguarde a verificação automática. O pacote completo já inclui o kit e suas
   bibliotecas. No pacote reduzido, siga a orientação exibida para cada requisito
   pendente.
3. Clique em Selecionar disco e instalar e escolha sua cópia USA SLUS-00583.
   Mantenha o `.cue` junto do `.bin` e com o nome correto do BIN em seu conteúdo.
4. A preparação começa assim que você seleciona o disco. Ela compila o jogo localmente e
   pode levar vários minutos. As etapas aparecem na janela; Ver registro abre
   os detalhes. O arquivo original permanece intacto.
5. Quando terminar, clique em Jogar. Nas próximas vezes, o atalho Jogar Duke
   TTK PT-BR abre direto. Use Configurar Duke TTK PT-BR para voltar ao assistente.

São aceitos os dumps USA conhecidos pelo projeto em MODE2/2352: CUE+BIN,
BIN/IMG bruto e IMG com os arquivos CloneCD correspondentes. Embora se use
popularmente o termo ISO, um `.iso` comum de setores de 2048 bytes, PAL ou
outra revisão não é aceito por este fluxo. Não basta renomear a extensão.

A primeira execução usa português, renderização OpenGL, precisão corrigida
de geometria/texturas, escala interna 2X e taxa AUTO. As execuções seguintes
preservam as preferências do jogador. WASD movimenta, mouse gira a câmera,
botão esquerdo atira, Espaço pula, E interage e Esc pausa.
O instalador inclui a tipografia HD dos menus no modo Modernizado com OpenGL.
As fontes são preparadas no computador do jogador. Os pacotes experimentais
de texturas da campanha e da HUD são usados nos testes locais da versão de desenvolvimento.

## Dados, atualização e problemas

- Aplicativo instalado: `%LOCALAPPDATA%\Programs\DukeTTK-PTBR`.
- Dados e compilação privada: `%LOCALAPPDATA%\DukeTTK-PTBR`.
- Cartões de memória: subpasta `saves`; preferências: subpasta `config`.
- Diagnóstico: `requirements.txt`, `requirements.json`, `setup.log` e
  `last-error.txt` na pasta de dados. Esses arquivos podem conter caminhos
  pessoais; revise antes de compartilhar.

Desinstalar remove o aplicativo e preserva os dados do jogador.
Para atualizar, execute o novo Setup na mesma pasta, abra **Configurar Duke TTK
PT-BR** e clique em **Preparar jogo**. O assistente reutiliza a cópia USA
já importada e recompila os arquivos locais. A atualização é manual.

Se a preparação falhar, consulte a mensagem, abra Ver registro e corrija o
requisito indicado antes de tentar novamente. Interromper a preparação não
modifica o disco original nem apaga saves. Não feche o assistente enquanto
o jogo estiver aberto.

## Gerar o pacote como mantenedor

Parta dos submódulos completos, patches aplicados e ferramentas autorais
`recomp/build-recompiler/psxrecomp-game.exe`, `psxrecomp-bios.exe` e
`recomp/build-tools/sector_check.exe` compiladas e testadas.
O empacotador usa Git apenas na máquina do mantenedor para selecionar fontes.

Instale o [Inno Setup oficial](https://jrsoftware.org/isdl.php) para gerar o
Setup. Na raiz do repositório, em PowerShell, com o Python de desenvolvimento:

```powershell
python recomp/tools/installer/package_windows.py --toolchain 'C:\caminho\cmake-clang-v1' --output 'C:\pacotes\duke-preview' --version 0.1.0-preview.3 --embed-toolchain --wheelhouse 'C:\caminho\wheels' --iscc 'C:\caminho\Inno Setup\ISCC.exe'
```

O diretório de saída precisa ser novo. `app` contém o pacote portátil;
`installer` contém o Setup. `--embed-toolchain` inclui o kit completo, evitando
seu download separado. As bibliotecas Python ainda precisam estar disponíveis:
para um pacote offline, use o Python x64 da mesma versão do kit para executar
`python -m pip download --only-binary=:all: -r recomp/requirements-local.txt -d <pasta-de-wheels>`.
Passe `--wheelhouse <pasta-de-wheels>` ao empacotador junto de
`--embed-toolchain`. Isso inclui kit e bibliotecas nos artefatos finais.
O pacote inclui o atlas de letras criado para o projeto. O mapeamento dos
glifos é gerado a partir do disco validado durante a preparação.
`--zip` também gera uma versão portátil.

O empacotamento inclui as licenças do projeto, OpenBIOS e ferramentas.
Não inclui executável do jogo já recompilado, código gerado do disco, packs
extraídos, BIOS comercial, imagens do jogo, saves ou cartões de memória.
O OpenBIOS livre é a exceção de firmware, acompanhado de sua licença.

O Setup é distribuído como prévia. A validação desta versão é local em Windows.
Desempenho e compatibilidade ainda dependem da máquina e do driver.
