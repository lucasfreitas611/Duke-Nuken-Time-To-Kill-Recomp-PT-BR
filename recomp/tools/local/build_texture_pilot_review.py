"""Build a local, self-contained comparison of real texture-pilot captures."""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
PROMPT = '''Use case: game texture remaster / asset edit. Image 1 is the exact edit target: a 32x32 diffuse wall texture from the user's owned Duke Nukem Time to Kill PS1 copy. Reconstruct this SAME texture faithfully at higher definition for a conservative game remaster. Square flat albedo texture, ideally 256x256 pixels, one texture filling the canvas edge to edge. Preserve the source's exact major layout: the muted dusty pink/salmon brickwork panel, brick row spacing and broad vertical aged gray trim at the sides; preserve all existing border widths, grout paths, relative shapes, overall brightness, warm/cool balance and recognizable weathering. Improve definition of the existing mortar, worn brick edges and restrained surface wear with deliberate hand-painted detail. Keep the late-1990s moody painted game-material character and strong readable large shapes. Restrained detail that still reads when reduced to 64 or 128 pixels. Uniform diffuse illumination, original subtle painted shading only, no new directional light or specular response. No photorealistic photographic noise, no glossy PBR look, no new symbols, text, windows, objects, perspective, bevelled 3D presentation, frames or comparison panels. No transparent pixels. Preserve the border pattern so adjacent original texture regions still join correctly. This is an in-game surface texture, not a screenshot or a concept illustration.'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--pilot', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    analysis = (ROOT / 'analysis').resolve()
    if output.exists() or not output.is_relative_to(analysis):
        parser.error('output must be a NEW directory under analysis')
    paths = [args.baseline.resolve(), args.pilot.resolve()]
    if not all(p.is_file() and p.is_relative_to(analysis) for p in paths):
        parser.error('measurements must be local pilot files under analysis')
    summaries = [json.loads(p.read_text(encoding='utf-8'))['summary'] for p in paths]
    images = ['data:image/png;base64,' + base64.b64encode(p.with_suffix('.png').read_bytes()).decode() for p in paths]
    assets = ROOT / 'analysis/remaster-assets/stone-a'
    compiled = (assets / 'remaster-2x.ttktx').read_bytes()
    fields = struct.unpack_from('<11I', compiled, 8)
    provenance = dict(generator='built-in image_gen', scope='single facade material pilot',
        original_size=[fields[5], fields[6]], runtime_size=list(fields[-2:]),
        compiled_bytes=len(compiled), prompt=PROMPT, performance_gate='60 FPS minimum not established',
        files={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in [assets/'original.png', assets/'remaster-v1.png', assets/'capture.json', assets/'remaster-2x.ttktx', *paths]},
        measurements=summaries)
    output.mkdir(parents=True)
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding='utf-8')
    (output / 'prompt.txt').write_text(PROMPT+'\n', encoding='utf-8')
    rows = []
    for name, getter in [
        ('Duração da amostra', lambda x: f"{x['seconds']:.1f} s"),
        ('Apresentações por segundo', lambda x: f"{x['presents_fps']:.2f}"),
        ('Imagens distintas por segundo', lambda x: f"{x['distinct_fps']:.2f}"),
        ('Quadro P95', lambda x: f"{x['cadence']['p95_us']/1000:.2f} ms"),
        ('Quadro P99', lambda x: f"{x['cadence']['p99_us']/1000:.2f} ms"),
        ('Falhas dos renderizadores auxiliares', lambda x: str(x['worker_failures']))]:
        rows.append('<tr><th>'+name+'</th>'+''.join('<td>'+getter(s)+'</td>' for s in summaries)+'</tr>')
    page = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Duke TTK - Piloto de textura</title><style>
:root{color-scheme:dark;font-family:Segoe UI,Arial,sans-serif;background:#111318;color:#e6e6e8}
body{margin:0 auto;padding:28px;max-width:1440px}h1{font-size:clamp(24px,4vw,38px);margin:10px 0}
p{max-width:900px;line-height:1.6;color:#bfc3cd}small,.eyebrow{color:#e6c357}.eyebrow{font-size:13px;letter-spacing:.12em}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:24px}.card{margin:0;min-width:0}
figcaption{padding:12px 0;font-weight:600}.view{aspect-ratio:16/9;overflow:hidden;background:black;border:1px solid #353942}
img{display:block;width:100%;height:100%;object-fit:contain;transform-origin:54% 32%;transition:transform .2s}
.zoom img{transform:scale(2)}button{font:inherit;color:#f4f4f5;background:#292d37;border:1px solid #626977;border-radius:6px;padding:10px 16px;cursor:pointer}
button:focus-visible{outline:3px solid #e6c357;outline-offset:3px}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:18px 0}
table{border-collapse:collapse;width:100%;max-width:900px;margin-top:22px}th,td{text-align:left;padding:12px;border-bottom:1px solid #353942}
thead th{color:#e6c357}tbody th{font-weight:400}a{color:#e6c357}pre{white-space:pre-wrap;font-size:13px;line-height:1.5}
@media(max-width:760px){body{padding:18px}.pair{grid-template-columns:1fr}th,td{padding:9px;font-size:14px}}
@media(prefers-reduced-motion:reduce){img{transition:none}}
</style><body><div class="eyebrow">PILOTO 01 / FACHADA DA FASE INICIAL</div>
<h1>Mais definição, o mesmo material</h1>
<p>Capturas reais do jogo. O piloto substitui uma textura de tijolos rosados de 32×32 por uma versão compilada em 64×64 texels. A iluminação e a geometria continuam sob o controle do jogo.</p>
<div class="controls"><button id="zoom" aria-pressed="false">Ampliar a fachada</button><small>NPCs e animações podem variar entre as capturas.</small></div>
<div class="pair" id="pair"><figure class="card"><figcaption>Original</figcaption><div class="view"><img alt="Fachada com a textura original" src="__BEFORE__"></div></figure>
<figure class="card"><figcaption>Piloto de textura 2X</figcaption><div class="view"><img alt="Mesma fachada com os tijolos remasterizados" src="__AFTER__"></div></figure></div>
<h2>Desempenho observado em 2X/AUTO</h2><p>As amostras sustentadas abaixo ainda não estabelecem 60 FPS mínimos. O piloto fica opcional enquanto o desempenho das cenas pesadas é validado.</p>
<table><thead><tr><th>Métrica</th><th>Original</th><th>Piloto</th></tr></thead><tbody>__ROWS__</tbody></table>
<p>Escopo desta etapa: um material da fachada. Personagens, menus, novas luzes e sombras ficam para etapas posteriores.</p>
<details><summary>Ficha da arte e da compilação</summary><p>Arte criada com ImageGen integrado. O mestre foi preservado; o compilador limitou a textura de execução a 64×64. O comparativo não é uma certificação de campanha completa.</p><pre>__META__</pre></details>
<script>document.getElementById('zoom').addEventListener('click',function(){const on=this.getAttribute('aria-pressed')!=='true';this.setAttribute('aria-pressed',String(on));this.textContent=on?'Mostrar visão geral':'Ampliar a fachada';document.getElementById('pair').classList.toggle('zoom',on)});</script></body></html>'''
    page = page.replace('__BEFORE__', images[0]).replace('__AFTER__', images[1]).replace('__ROWS__', ''.join(rows))
    page = page.replace('__META__', html.escape(json.dumps(provenance, indent=2, ensure_ascii=False)))
    (output / 'index.html').write_text(page, encoding='utf-8')
    print((output / 'index.html').relative_to(ROOT))


if __name__ == '__main__':
    main()
