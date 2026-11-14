"""Compile generated atlas candidates into UV-mapped PNGs and a local review.

This only packs generated art. It does not author pixels, enable replacements,
change original media or certify UV/performance acceptance.
"""
import hashlib
import html
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'recomp/analysis/level00-art-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((OUT/'atlas-plan.json').read_text(encoding='utf-8'))
    review = json.loads((OUT/'art-review.json').read_text(encoding='utf-8')) if (OUT/'art-review.json').exists() else {}
    (OUT/'diffuse-2x').mkdir(exist_ok=True)
    (OUT/'diffuse-4x').mkdir(exist_ok=True)
    atlas_info = {}
    materials = []
    cards = []
    for item in plan['materials']:
        a,c = item['atlas'], item['cell']
        alt = review.get('alternate_atlases',{}).get(str(a),{})
        override = review.get('cell_overrides',{}).get(item['id'],{})
        master = OUT/override.get('master',alt.get('master',f'master-atlas-{a:02d}.png'))
        prompt = override.get('prompt',alt.get('prompt',f'prompt-atlas-{a:02d}.txt'))
        entry = dict(item)
        entry['art_master'] = master.name
        entry['prompt'] = prompt
        entry['alternate_costume'] = bool(alt)
        if override:
            entry['revision_reason'] = override['reason']
        if alt:
            entry['alternate_costume_details'] = alt
        entry['runtime_enabled'] = False
        entry['uv_verified_in_game'] = False
        entry['performance_verified'] = False
        if master.exists():
            if master.name not in atlas_info:
                with Image.open(master) as im:
                    im.verify()
                atlas_info[master.name] = dict(file=master.name,sha256=sha(master),
                                     prompt=prompt,
                                     method='built-in image_gen',status='art-candidate-needs-UV-review')
            with Image.open(master) as im:
                w,h = im.size
                # Integer grid partition. Never overwrite the generated master.
                x,y = c%4,c//4
                tile = im.convert('RGB').crop((round(x*w/4),round(y*h/4),round((x+1)*w/4),round((y+1)*h/4)))
                entry['generated_cell_size'] = list(tile.size)
            for scale in (2,4):
                target=OUT/f'diffuse-{scale}x'/f'{item["id"]}.png'
                size=tuple(v*scale for v in item['native_size'])
                tile.resize(size,Image.Resampling.LANCZOS).save(target)
                entry[f'diffuse_{scale}x'] = target.relative_to(OUT).as_posix()
                entry[f'sha256_{scale}x'] = sha(target)
            entry['status']='art-candidate-needs-UV-review'
            # Existing lettering drift and packed-island drift must be inspected.
            entry['review_required']=['UV alignment','tiling seams','lettering if present',
                                      'original cutout and STP retained by renderer','in-game brightness',
                                      'animated frame consistency if applicable']
        else:
            entry['status']='pending-art'
        materials.append(entry)
        title = html.escape(item['id'])
        image = entry.get('diffuse_4x',item['reference'])
        cards.append(f'<article data-kind="{"world" if item["world"] else "model"}"><h3>{title}</h3>'
                     f'<div class="pair"><figure><a href="{item["reference"]}"><img alt="Referencia original" loading="lazy" src="{item["reference"]}"></a><figcaption>Original</figcaption></figure>'
                     f'<figure><a href="{image}"><img alt="Arte para revisao" loading="lazy" src="{image}"></a><figcaption>{"Arte candidata" if "diffuse_4x" in entry else "Pendente"}</figcaption></figure></div>'
                     f'<p>{item["native_size"][0]} x {item["native_size"][1]} nativo | atlas {a:02d}, celula {c} | '
                     f'{"cenario" if item["world"] else "modelo"}'
                     f'{" | FIGURINO ALTERNATIVO" if alt else ""}</p></article>')
    ready=sum(x['status']!='pending-art' for x in materials)
    world=sum(x['world'] and x['status']!='pending-art' for x in materials)
    alternatives=sum(x['alternate_costume'] and x['status']!='pending-art' for x in materials)
    result=dict(scope=plan['scope'],generation='built-in image_gen',
                note='Candidates only. RGB exports do not replace native transparency/STP. Atlas AI can move islands or change signs. No 60 FPS claim.',
                counts=dict(materials=len(materials),art_candidates=ready,world_candidates=world,
                            world_total=plan['world_materials'],pending_art=len(materials)-ready,
                            reference_based_candidates=ready-alternatives,
                            alternate_costume_candidates=alternatives,
                            original_reference_pending_alternative_available=alternatives,in_game_approved=0),
                model_decode_errors=plan['model_errors'],decoder_repairs=plan.get('decoder_repairs',[]),
                source_files=plan.get('source_files',{}),world_runs=plan.get('world_runs',[]),
                art_review=review,atlases=atlas_info,materials=materials)
    (OUT/'coverage.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Primeira fase - revisao de texturas</title><style>
body{background:#14171c;color:#eef0f3;font:16px system-ui;margin:24px;max-width:1800px}h1{font-size:30px}p{line-height:1.5;color:#bfc6d1}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}article{background:#20252e;padding:14px;border-radius:10px}h3{margin:0 0 12px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}figure{margin:0}img{width:100%;height:180px;object-fit:contain;background:#30343b}figcaption{color:#bfc6d1;padding-top:6px}
button{padding:10px 16px;margin:0 8px 18px 0;border:0;border-radius:6px;cursor:pointer}a{color:#8dc9ff}article p{font-size:12px}
</style><h1>Primeira fase: artes candidatas</h1>'''
    page+=f'<p>{ready} de {len(materials)} materiais com arte. Cenario: {world} de {plan["world_materials"]}. Nenhum aprovado no jogo nesta etapa.</p>'
    page+=f'<p>{alternatives} recortes sao uma proposta separada de figurino fechado verde-azulado. Duas folhas com referencia original ficaram pendentes apos bloqueio da ferramenta de imagens; essas alternativas foram criadas sem as referencias bloqueadas. Nao sao uma reproducao do figurino original.</p>'
    page+='<p>As imagens foram geradas a partir das referencias locais. Recortes 2X e 4X sao formatos de exportacao, nao garantia de detalhe nativo nessas resolucoes. Letreiros, ilhas UV, emendas, animacoes e transparencias exigem revisao. A ativacao e os testes de FPS sao etapas separadas.</p>'
    page+='<p><a href="coverage.json">Manifesto e cobertura</a> | <a href="atlas-plan.json">Mapa das coordenadas nativas</a></p>'
    page+=''.join(f'<button onclick="filterCards(\'{kind}\')">{label}</button>' for kind,label in [('all','Todos'),('world','Cenario'),('model','Modelos')])
    page+='<main class="grid">'+''.join(cards)+'</main><script>function filterCards(k){document.querySelectorAll("article").forEach(e=>e.hidden=k!=="all"&&e.dataset.kind!==k)}</script></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(result['counts']))


if __name__=='__main__':
    main()
