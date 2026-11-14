"""Local review of complete DB00 generated art and optional spatial smoothing."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'recomp/analysis/level00-realistic-complete'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    runs={name:json.loads((OUT.parent/name/'measurement.json').read_text())['summary']
          for name in ('texture-complete-off','texture-complete-smooth-opt')}
    lifecycle=json.loads((OUT.parent/'texture-complete-smooth-opt/lifecycle.json').read_text())
    patch=json.loads((OUT.parent/'texture-complete-checks/runtime-patch-verification.json').read_text())
    result=dict(materials=manifest['materials'],references=manifest['references'],
                installed_material_ids=sorted({e['id'] for e in manifest['entries']}),
                runs=runs,lifecycle=lifecycle,framework_patch=patch,
                binary_sha256=hashlib.sha256((ROOT/'recomp/build-local/Duke_Nukem__Time_to_Kill_Recompiled.exe').read_bytes()).hexdigest(),
                automated_checks=dict(profile_tests=113,texture_tests=6,invalidation_region_comparisons=1024*1024,
                                      near_native=True,ptbr_native=True),
                limits=['All generated DB00 art installed; not all models, animations and rooms visually approved',
                        'First-level gameplay only; menus without generated art stay native',
                        '32 materials use the previously generated alternate clothed costumes',
                        'Exact source/CLUT, UV admission and native texture-window gates still apply',
                        'Water and prolonged heavy combat not certified at a minimum of 60 FPS',
                        'Live captures have different actor positions, some different window sizes; not pixel-aligned comparisons'])
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Texturas completas e antisserrilhamento</title><style>
body{background:#151820;color:#eef2f6;font:16px system-ui;margin:24px;max-width:1700px}p{line-height:1.6}.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}figure{margin:0}img{width:100%}figcaption{padding:12px}a{color:#9dd4ff}td,th{padding:12px;border-bottom:1px solid #566}table{border-collapse:collapse}
</style><h1>Todas as artes geradas da primeira fase</h1>
<p>665 materiais, 726 referencias de uso. Cenario, modelos, inimigos e armas usam recortes diretamente das imagens geradas, sem a reducao para 2X. Os 32 materiais de figurinos alternativos tambem estao incluidos. Instalacao completa nao significa aprovacao visual de todos os modelos, animacoes e salas. Menus sem arte gerada continuam originais.</p>
<p>Abra Jogar com Texturas Realistas.cmd: texturas completas e antisserrilhamento Suave. Testar Textura Remasterizada.cmd abre o mesmo pacote. Nas opcoes avancadas de graficos, Arte das texturas e Antisserrilhamento sao independentes. Alteracoes valem ao reabrir. Jogar com Texturas Originais.cmd desliga ambos.</p>
<p>Suave combina filtragem linear das novas texturas, dois niveis de mipmap e suavizacao espacial de bordas na apresentacao. Isso pode suavizar detalhes muito pequenos. Nao altera geometria, iluminacao, velocidade do jogo ou controles.</p><section class="pair">'''
    for name,label in [('texture-pack-hd-original','Originais: captura anterior'),('texture-complete-off','Todas as artes, suavizacao desligada'),('texture-complete-smooth-opt','Todas as artes, suavizacao ligada')]:
        path=f'../{name}/measurement.png'
        page+=f'<figure><a href="{path}"><img alt="{label}" src="{path}"></a><figcaption>{label}</figcaption></figure>'
    page+='</section><h2>Medicoes da versao final</h2><table><tr><th>Suavizacao</th><th>Segundos</th><th>Imagens novas/s</th><th>Falhas de desenho</th></tr>'
    for name,r in runs.items():
        page+=f'<tr><td>{"Ligada" if name.endswith("opt") else "Desligada"}</td><td>{r["seconds"]}</td><td>{r["distinct_fps"]}</td><td>{r["worker_failures"]}</td></tr>'
    page+='</table><p>OpenGL 2X/AUTO, saves e entradas privados. A media nao garante minimo constante de 60 FPS. As cenas variam entre sessoes e estas rodadas nao demonstram ganho de desempenho. Agua e combate pesado ainda precisam de validacao.</p>'
    page+='<p>A primeira tentativa completa ficou em 45,62 imagens novas/s. A versao final limita a verificacao a materiais observados e usa um indice espacial de invalidacao. A identidade original e conferida novamente sempre que fonte ou paleta mudam, inclusive em replay e restauracao de estado.</p>'
    page+='<h2>Outros angulos e transicoes</h2><section class="pair">'
    for file,label in [('turned.png','Camera girada, arma e inimigos'),('level-6.png','Outra fase: artes nativas'),('after-save-load.png','Primeira fase restaurada')]:
        path='../texture-complete-smooth-opt/'+file
        page+=f'<figure><a href="{path}"><img loading="lazy" alt="{label}" src="{path}"></a><figcaption>{label}</figcaption></figure>'
    page+='</section><p>Transicoes de teste por comando 0 - 6 - 0 e restauracao de checkpoint privado: sem falhas de desenho ou worker registradas. Nao substituem testar a campanha naturalmente.</p>'
    page+='<p>Pacote RGB: aproximadamente 204 MiB. Nesta maquina, atlas 8748 x 8748 com bordas protegidas e mipmaps: aproximadamente 287 MiB RGB de armazenamento grafico nominal. Placas com limite menor reduzem a resolucao de cada recorte. Falha de alocacao conserva as texturas nativas.</p>'
    page+='<p><a href="manifest.json">Materiais e origem das artes</a> | <a href="verification.json">Resultados, testes e limites</a></p></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print('recomp/analysis/level00-realistic-complete/index.html')


if __name__=='__main__':main()
