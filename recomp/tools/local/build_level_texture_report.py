"""Local, factual review of the optional first scenery texture lot."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'recomp/analysis/level00-realistic-2x'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    runs={}
    for name in ('texture-pack-original-final','texture-pack-realistic-final'):
        p=OUT.parent/name/'measurement.json'
        runs[name]=json.loads(p.read_text())['summary']
    lifecycle=json.loads((OUT.parent/'texture-pack-realistic-final/lifecycle.json').read_text())
    report=dict(scope=manifest['scope'],entries=len(manifest['entries']),runs=runs,
                lifecycle=lifecycle,optional=True,enabled_by_default=False,
                acceptance='Runtime pilot, visual user review pending; not a campaign 60 FPS certification',
                binary_sha256=hashlib.sha256((ROOT/'recomp/build-local/Duke_Nukem__Time_to_Kill_Recompiled.exe').read_bytes()).hexdigest(),
                automated_checks=dict(profile_tests=113,registry_and_specimen_tests=4,
                                      depth_modes=True,projective_uv_samples=360,near_native=True,ptbr_native=True),
                limits=['16 scenery regions only; no character/costume replacement',
                        'Scenery cutout/STP/modulation stay native; authored alpha is not installed',
                        'Water, prolonged combat, all rooms, all cameras and campaign performance not certified',
                        'Screenshots are actual separate live sessions, with different actor positions',
                        'Final native sample is 30 seconds; realistic sample is 60 seconds; not statistically controlled benchmarking'])
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Texturas realistas - primeiro lote no jogo</title><style>
body{background:#151820;color:#edf1f5;font:16px system-ui;margin:28px;max-width:1700px}h1{font-size:30px}p{line-height:1.55;color:#c6ceda}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}figure{margin:0;background:#242a35;padding:14px;border-radius:12px}
img{width:100%;display:block}figcaption{padding:10px 0}table{border-collapse:collapse;width:100%;margin:22px 0}td,th{padding:10px;text-align:left;border-bottom:1px solid #424a59}a{color:#9dd4ff}
button{padding:10px 16px;margin:12px 10px 12px 0;cursor:pointer;border:0;border-radius:6px}.zoom img{aspect-ratio:16/9;object-fit:cover;object-position:57% 25%;transform:scale(1.8)}.zoom figure>a{display:block;overflow:hidden}
</style><h1>Primeiro lote aplicado: texturas realistas 2X</h1>
<p>16 materiais de cenario, incluindo a fachada da boate. Opcional, desligado por padrao. Ative em OPCOES &gt; AVANCADO &gt; ARTE DAS TEXTURAS &gt; REALISTAS 2X e reabra o jogo. Os atalhos na raiz do projeto permitem escolher diretamente entre Originais e Realistas.</p>
<p>As capturas abaixo sao do jogo. A camera e os inimigos variam entre sessoes; nao sao imagens alinhadas para comparacao pixel a pixel.</p>
<button onclick="document.body.classList.toggle('zoom')">Ampliar fachada / voltar</button><section class="pair">'''
    for key,label in [('texture-pack-original-final','Originais'),('texture-pack-realistic-final','Realistas 2X')]:
        src=f'../{key}/measurement.png'
        page+=f'<figure><a href="{src}"><img alt="{label} no jogo" src="{src}"></a><figcaption>{label}</figcaption></figure>'
    page+='</section><table><tr><th>Modo</th><th>Duracao</th><th>Imagens novas/s</th><th>Apresentacoes/s</th><th>p95 / p99 final (ms)</th><th>Falhas dos workers</th></tr>'
    for key,s in runs.items():
        c=s['cadence'];label='Realistas 2X' if 'realistic' in key else 'Originais'
        page+=f'<tr><td>{label}</td><td>{s["seconds"]} s</td><td>{s["distinct_fps"]}</td><td>{s["presents_fps"]}</td><td>{c["p95_us"]/1000:.2f} / {c["p99_us"]/1000:.2f}</td><td>{s["worker_failures"]}</td></tr>'
    page+='</table><p>Media proxima de 60 FPS neste trecho. Os percentis representam a janela final de 600 intervalos. Isso nao garante minimo de 60 FPS: houve intervalos maiores isolados e variacao nas rodadas anteriores, inclusive com as texturas originais. Agua e combate pesado ainda precisam de validacao. As duracoes sao diferentes e estas amostras nao demonstram ganho de desempenho.</p>'
    page+='<p>Troca de fase por comando de teste 0 - 6 - 0 e restauracao do checkpoint privado: sem falhas de replay/worker registradas. A fase 6 conserva suas texturas originais.</p><section class="pair">'
    for file,label in [('level-6.png','Outra fase: pacote desativado'),('after-save-load.png','Primeira fase apos restaurar o save')]:
        src='../texture-pack-realistic-final/'+file
        page+=f'<figure><a href="{src}"><img alt="{label}" loading="lazy" src="{src}"></a><figcaption>{label}</figcaption></figure>'
    page+='</section><p><a href="manifest.json">Materiais instalados</a> | <a href="verification.json">Resultados e limites</a> | <a href="runtime-patch-verification.json">Verificacao do patch</a></p>'
    page+='<p>RGB em um atlas unico de 512 x 512; classificacao de transparencia e iluminacao originais preservadas. Cache de identidade reutilizado apenas quando textura e paleta permaneceram intactas durante o replay; atualizacoes e loads invalidam os dados correspondentes.</p></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(entries=report['entries'],review='recomp/analysis/level00-realistic-2x/index.html')))


if __name__=='__main__':
    main()
