"""Build a local review from the expanded texture pilot's actual captures."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'recomp/analysis/level00-realistic-hd'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    runs={}
    for name in ('texture-pack-hd-original','texture-pack-hd-review'):
        runs[name]=json.loads((OUT.parent/name/'measurement.json').read_text())['summary']
    lifecycle=json.loads((OUT.parent/'texture-pack-hd-review/lifecycle.json').read_text())
    result=dict(scope=manifest['scope'],entries=len(manifest['entries']),runs=runs,
                lifecycle=lifecycle,art_source='Generated master cells, not 2X exports',
                binary_sha256=hashlib.sha256((ROOT/'recomp/build-local/Duke_Nukem__Time_to_Kill_Recompiled.exe').read_bytes()).hexdigest(),
                checks=dict(profiles=113,specimen_and_registry=4,near_native=True,ptbr_native=True),
                limits=['Scenery only, 64 of 168 first-level world material groups',
                        'Original geometry, cutout, STP, vertex lighting and actors retained',
                        'No minimum 60 FPS guarantee; water and prolonged heavy combat unverified',
                        'Live sessions have different actor positions; not pixel-aligned captures',
                        'Native baseline cadence varied between sessions; these runs do not establish a performance gain from HD',
                        'Generated packed UV regions and seams still need player aesthetic review'])
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Texturas realistas HD - comparacao no jogo</title><style>
body{background:#151820;color:#eef2f6;font:16px system-ui;margin:24px;max-width:1700px}p{line-height:1.6}.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}figure{margin:0}img{width:100%}figcaption{padding:12px}a{color:#9dd4ff}td,th{padding:12px;border-bottom:1px solid #566}table{border-collapse:collapse}
</style><h1>Texturas realistas HD: capturas do jogo</h1>
<p>Pacote ampliado de 16 para 64 materiais de cenario. Recortes retirados diretamente dos masters gerados: uma textura comum de 32 x 32 agora usa 320 x 320, em vez de 64 x 64 do piloto anterior. Fachadas, asfalto, calcadas e grama da area inicial agora recebem arte. Personagens, armas, HUD e iluminacao continuam originais.</p>
<p>Use Jogar com Texturas Realistas.cmd ou Testar Textura Remasterizada.cmd na raiz do projeto. O segundo agora aponta para o mesmo pacote HD. No menu: Arte das texturas &gt; Realistas HD, depois reabra o jogo. Para voltar, use Jogar com Texturas Originais.cmd.</p><section class="pair">'''
    for name,label in [('texture-pack-hd-original','Originais'),('texture-pack-realistic-final','Piloto anterior: 16 texturas 2X'),('texture-pack-hd-review','Novo pacote: 64 texturas HD')]:
        path=f'../{name}/measurement.png'
        page+=f'<figure><a href="{path}"><img alt="{label}" src="{path}"></a><figcaption>{label}</figcaption></figure>'
    page+='</section><h2>Medicoes nesta maquina</h2><table><tr><th>Modo</th><th>Segundos</th><th>Imagens novas/s</th><th>Falhas de desenho</th></tr>'
    for name,r in runs.items():
        page+=f'<tr><td>{"HD" if name.endswith("review") else "Original"}</td><td>{r["seconds"]}</td><td>{r["distinct_fps"]}</td><td>{r["worker_failures"]}</td></tr>'
    page+='</table><p>Configuracao OpenGL 2X/AUTO, saves e entradas privados. Media nao e minimo garantido de 60 FPS. Cenas e atores variam entre sessoes. A rodada original teve menor cadencia de imagens novas, variacao tambem observada antes deste pacote. Estes testes nao demonstram ganho de desempenho causado pelas texturas HD. Agua e combate pesado ainda precisam de validacao.</p><p>Atlas de RGB: 4096 x 4096, aproximadamente 48 MiB. O pacote ocupa mais memoria grafica que o piloto anterior. Imagens geradas preservadas; arquivos originais do jogo e saves do jogador nao foram alterados.</p>'
    page+='<p><a href="manifest.json">Materiais e origem das artes</a> | <a href="verification.json">Resultados e limites</a></p></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print('recomp/analysis/level00-realistic-hd/index.html')


if __name__=='__main__':
    main()
