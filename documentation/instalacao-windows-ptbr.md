# Instalação assistida no Windows

O assistente `DukeTTK-PTBR.exe` prepara o jogo usando a cópia original do
jogador. O pacote contém ferramentas e código do projeto; o executável do jogo
e os recursos extraídos são gerados no computador do jogador. Não exige clonar
o GitHub, instalar Git ou executar comandos de compilação manualmente.

Na página de Releases, abra **Assets** e baixe o arquivo
`DukeTTK-PTBR-<versão>-Setup.exe`.
[Releases do projeto](https://github.com/lucasfreitas611/Duke-Nuken-Time-To-Kill-Recomp-PT-BR/releases)

## Atualizações da preview.7

- Assistente com uma ação principal por etapa, mensagens de erro e barra de
  progresso. Os componentes incluídos são instalados automaticamente, offline.
- Bloqueio de preparação sem disco selecionado ou previamente importado.
  Discos incompatíveis são recusados antes da recompilação.
- Perfil gráfico Full HD, HUD, ícones e fonte dos menus remasterizados.
  O menu de vídeo permite alternar entre as texturas originais e remasterizadas.
- Navegação por mouse nos menus e gravação das preferências no Windows.
- Encerramento da conexão de diagnóstico e do assistente ao fechar o jogo,
  liberando a próxima abertura pelo atalho.
- Uso do Python privado durante a atualização do compilador, incluindo a
  reconfiguração do cache do CMake.

Validação local em Windows em 2026-11-19: 14 testes do instalador e 114 de
preferências passaram. O assistente foi exercitado com uma pasta nova,
instalação automática de componentes, seleção cancelada e discos inválidos.
A preparação completa usando uma cópia USA foi concluída em uma pasta de
teste. Duas aberturas consecutivas pelo atalho terminaram com o encerramento
dos processos do jogo e do assistente.

## Para jogar

1. Execute o Setup e mantenha marcada a opção de abrir o assistente.
2. Clique em **Escolher disco** e selecione o arquivo da sua cópia original
   USA (SLUS-00583). Se escolher o `.cue`, mantenha o `.bin` na mesma pasta.
3. Aguarde a verificação e a preparação. O instalador já traz os componentes
   necessários e configura tudo automaticamente, mesmo sem internet. A barra
   mostra o avanço durante a recompilação.
4. Quando aparecer **Jogo pronto**, clique em **Jogar**. Depois, use o atalho
   **Duke Nuken TTK - Recomp**. O assistente fecha ao sair do jogo.

O assistente pede uma nova seleção quando o disco é incompatível ou está
incompleto. Se faltar espaço ou o driver gráfico for incompatível, ele pausa
o fluxo e informa o que precisa ser corrigido. Consulte **Ver detalhes** se
precisar do registro técnico.

O pacote exige Windows 10 ou 11 x64, um driver com OpenGL 3.3 e 8 GB livres
para a primeira preparação. A pasta de dados deve permitir gravação. O
instalador inclui Python, CMake, Ninja, Clang e as bibliotecas necessárias em
um ambiente privado do jogo.

São aceitos os dumps USA conhecidos pelo projeto em MODE2/2352: CUE+BIN,
BIN/IMG bruto e IMG com os arquivos CloneCD correspondentes. Embora se use
popularmente o termo ISO, um `.iso` comum de setores de 2048 bytes, PAL ou
outra revisão não é aceito por este fluxo. Não basta renomear a extensão.

A primeira execução usa o perfil gráfico de **Jogar em Full HD.cmd**: tela sem
bordas, largura de referência de 1920, formato 16:9, OpenGL, precisão corrigida
de geometria/texturas, escala interna 2X, suavização, VSync e taxa AUTO. Ao
atualizar uma instalação anterior, esse perfil gráfico é aplicado uma vez,
preservando a escolha entre texturas originais e remasterizadas. A partir daí,
as opções alteradas pelo jogador ficam salvas. WASD movimenta, mouse gira a câmera,
botão esquerdo atira, Espaço pula, E interage e Esc pausa.
O instalador completo inclui a tipografia dos menus, o HUD, os ícones e as texturas
remasterizadas já mapeadas para a campanha. Os bancos são preparados no
computador do jogador. Em **Opções > Vídeo > Estilo das texturas**, escolha
**Original** ou **Remasterizadas** e clique em **Confirmar**. Use OpenGL.

O mouse destaca as opções quando passa sobre elas. Clique para abrir uma
opção, alterar um valor ou acionar um botão no rodapé. O botão direito volta
e a roda navega pela lista ou ajusta o controle selecionado.

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

Se a preparação falhar, consulte a mensagem, abra **Ver detalhes** e corrija o
requisito indicado antes de tentar novamente. Interromper a preparação não
modifica o disco original nem apaga saves.

## Gerar o pacote como mantenedor

Parta dos submódulos completos, patches aplicados e ferramentas autorais
`recomp/build-recompiler/psxrecomp-game.exe`, `psxrecomp-bios.exe` e
`recomp/build-tools/sector_check.exe` compiladas e testadas.
O empacotador usa Git apenas na máquina do mantenedor para selecionar fontes.

Instale o [Inno Setup oficial](https://jrsoftware.org/isdl.php) para gerar o
Setup. Na raiz do repositório, em PowerShell, com o Python de desenvolvimento:

```powershell
python recomp/tools/installer/export_remastered_art.py recomp/analysis/installer-remastered-art.zip
python recomp/tools/installer/package_windows.py --toolchain 'C:\caminho\cmake-clang-v1' --output 'C:\pacotes\duke-preview' --embed-toolchain --wheelhouse 'C:\caminho\wheels' --remastered-art recomp/analysis/installer-remastered-art.zip --iscc 'C:\caminho\Inno Setup\ISCC.exe'
```

O diretório de saída precisa ser novo. `app` contém o pacote portátil;
`installer` contém o Setup. `--embed-toolchain` inclui o kit completo, evitando
seu download separado. Para preparar o pacote de bibliotecas, use o Python
x64 da mesma versão do kit para executar
`python -m pip download --only-binary=:all: -r recomp/requirements-local.txt -d <pasta-de-wheels>`.
Passe `--wheelhouse <pasta-de-wheels>` ao empacotador junto de
`--embed-toolchain`. Isso inclui kit e bibliotecas nos artefatos finais.
O pacote inclui o atlas de letras criado para o projeto. O mapeamento dos
glifos é gerado a partir do disco validado durante a preparação.
`--remastered-art` incorpora a arte de substituição e as coordenadas dos 32
bancos e as artes do HUD e dos ícones. O exportador usa os pacotes locais
revisados em `recomp/analysis`.
As palavras de VRAM e as paletas são lidas do disco do jogador na instalação.
`--zip` também gera uma versão portátil.

O empacotamento inclui as licenças do projeto, OpenBIOS e ferramentas.
Não inclui executável do jogo já recompilado, código gerado do disco, packs
extraídos, BIOS comercial, imagens do jogo, saves ou cartões de memória.
O OpenBIOS livre é a exceção de firmware, acompanhado de sua licença.

O Setup é distribuído como prévia. A validação desta versão é local em Windows.
Desempenho e compatibilidade ainda dependem da máquina e do driver.
