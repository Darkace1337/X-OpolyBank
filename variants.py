"""Discover local edition folders and their optional PNG player pieces."""
import json
from pathlib import Path
from urllib.parse import quote
from property_data import load_properties, safe_name

VARIANTS_ROOT=Path(__file__).resolve().parent/'Variants'
CLASSIC={'hat':'Top hat','car':'Race car','ship':'Battleship','dog':'Scottie dog','cat':'Cat','duck':'Rubber duck','penguin':'Penguin','rex':'T-Rex','thimble':'Thimble','boot':'Boot','iron':'Iron','wheelbarrow':'Wheelbarrow','horse':'Horse & rider','money':'Money bag','cannon':'Cannon'}
LEGACY_PIECES={'hello-kitty':'Hello Kitty','my-melody':'My Melody','kuromi':'Kuromi','keroppi':'Keroppi','pompompurin':'Pompompurin','cinnamoroll':'Cinnamoroll','badtz-maru':'Badtz-maru'}

def classic_pieces():
    return [dict(id=k,label=v,url=f'/icons/{k}.svg',group='Classic pieces',extra=False) for k,v in CLASSIC.items()]

def discover_variants(root=None):
    root=Path(root or VARIANTS_ROOT)
    result=[]
    if not root.exists(): return result
    for folder in sorted(root.iterdir(),key=lambda p:(p.name!='Normal',p.name.casefold())):
        if not folder.is_dir() or folder.is_symlink() or folder.name.startswith('.'): continue
        item=dict(name=folder.name,pieces=[],error=None,settings={'luxuryTaxName':'Luxury Tax'})
        try:
            csv=folder/'properties.csv'
            if csv.is_symlink(): raise ValueError('properties.csv must be a local file.')
            item['properties']=load_properties(csv)
            settings=folder/'settings.json'
            if settings.exists():
                if settings.is_symlink():raise ValueError('settings.json must be a local file.')
                data=json.loads(settings.read_text())
                if not isinstance(data,dict):raise ValueError('settings.json must contain an object.')
                if 'luxuryTaxName' in data:item['settings']['luxuryTaxName']=safe_name(data['luxuryTaxName'])
            for png in sorted(folder.iterdir(),key=lambda p:p.name.casefold()):
                if png.suffix.lower()!='.png' or not png.is_file() or png.is_symlink():continue
                if png.stat().st_size>5_000_000: raise ValueError(f'{png.name} exceeds 5 MB.')
                with png.open('rb') as f:
                    if f.read(8)!=b'\x89PNG\r\n\x1a\n':raise ValueError(f'{png.name} is not a PNG image.')
                item['pieces'].append(dict(id=f'variant:{folder.name}:{png.name}',label=png.stem,
                    url=f'/variant-icons/{quote(folder.name,safe="")}/{quote(png.name,safe="")}',group=folder.name,extra=True))
        except (ValueError,OSError) as e:
            item['error']=str(e);item['properties']=[];item['pieces']=[]
        result.append(item)
    return result

def get_variant(name,root=None):
    item=next((v for v in discover_variants(root) if v['name']==name),None)
    if not item:raise ValueError('Choose an available variant.')
    if item['error']:raise ValueError(f"{name}: {item['error']}")
    return item

def variant_icon_path(name,filename,root=None):
    # Serve only a discovered PNG in an immediate variant folder, never arbitrary paths.
    item=get_variant(name,root)
    if not any(p['id']==f'variant:{name}:{filename}' for p in item['pieces']):raise ValueError('Icon not found.')
    return Path(root or VARIANTS_ROOT)/name/filename
