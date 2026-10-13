"""CSV property definitions and strict import/export validation (stdlib only)."""
import csv,io,re
from pathlib import Path
COLORS={'brown':'#955c3f','light_blue':'#64c5e8','pink':'#d94c98','orange':'#f09a38','red':'#e84c4c','yellow':'#e8cc42','green':'#3eb888','dark_blue':'#527ce6'}
FIELDS=['id','name','kind','group','purchase_price','mortgage_value','house_cost','hotel_cost','set_multiplier','rent_base','rent_1_house','rent_2_houses','rent_3_houses','rent_4_houses','rent_hotel','railroad_rent_1','railroad_rent_2','railroad_rent_3','railroad_rent_4','utility_multiplier_1','utility_multiplier_2']
def safe_name(value):
    value=str(value).strip()
    if not value or len(value)>60 or value[0] in '=+-@' or any(ord(c)<32 for c in value):
        raise ValueError('Names must be 1–60 characters, without spreadsheet formulas or control characters.')
    return value

def parse_properties(text):
    if not isinstance(text,str) or len(text.encode('utf-8'))>50000: raise ValueError('CSV must be UTF-8 text under 50 KB.')
    try:
        text=text.replace('mono'+'poly_multiplier','set_multiplier',1)
        reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')),strict=True)
        if not reader.fieldnames or len(reader.fieldnames)!=len(FIELDS) or set(reader.fieldnames)!=set(FIELDS):
            raise ValueError('CSV headers must match the downloaded template exactly.')
        result=[]; ids=set(); names=set()
        for line,row in enumerate(reader,2):
            if len(result)>=128: raise ValueError('Maximum 128 properties.')
            def err(msg): raise ValueError(f'CSV row {line}: {msg}')
            if None in row or any(v is None for v in row.values()):err('Wrong number of columns.')
            row={k:v.strip() for k,v in row.items()}
            def number(key):
                if not re.fullmatch(r'[0-9]+',row[key]):err(f'{key} must be a nonnegative whole number (no currency symbols or formulas).')
                value=int(row[key])
                if value>1000000:err(f'{key} must be at most 1000000.')
                return value
            pid=row['id']; kind=row['kind']; group=row['group']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',pid):err('Invalid id; use letters, digits, hyphens or underscores.')
            if pid in ids:err('Duplicate id.')
            try:name=safe_name(row['name'])
            except ValueError as e:err(str(e))
            if name.casefold() in names:err('Duplicate property name.')
            if kind not in ['street','railroad','utility']:err('kind must be street, railroad or utility.')
            if (kind=='street' and group not in COLORS) or (kind!='street' and group!=kind):err('Invalid group for this kind.')
            required=(FIELDS[6:15] if kind=='street' else FIELDS[15:19] if kind=='railroad' else FIELDS[19:21])
            for k in FIELDS[6:]:
                if k not in required and row[k]:err(f'{k} must be blank for a {kind}.')
            p=dict(id=pid,name=name,kind=kind,group=COLORS.get(group,group),color=COLORS.get(group,'#ffffff' if kind=='railroad' else '#000000'),price=number('purchase_price'),mortgageValue=number('mortgage_value'),houseCost=0,hotelCost=0,setMultiplier=2,rents=[],railroadRents=[],utilityMultipliers=[],owner=None,mortgaged=False,houses=0)
            if p['mortgageValue']>p['price']:err('Mortgage value cannot exceed purchase price.')
            if kind=='street':p.update(houseCost=number('house_cost'),hotelCost=number('hotel_cost'),setMultiplier=number('set_multiplier'),rents=[number(k) for k in FIELDS[9:15]])
            elif kind=='railroad':p['railroadRents']=[number(k) for k in FIELDS[15:19]]
            else:p['utilityMultipliers']=[number(k) for k in FIELDS[19:21]]
            ids.add(pid);names.add(name.casefold());result.append(p)
        if not result:raise ValueError('CSV contains no properties.')
        if sum(p['kind']=='railroad' for p in result)>4 or sum(p['kind']=='utility' for p in result)>2:raise ValueError('This format supports up to four railroads and two utilities.')
        return result
    except csv.Error as e:raise ValueError(f'Invalid CSV: {e}') from e

def load_properties(path):return parse_properties(Path(path).read_text(encoding='utf-8-sig'))
def migrate_property(p):
    legacy=p.pop('mono'+'polyMultiplier',2);p.setdefault('setMultiplier',legacy)
    p.setdefault('mortgageValue',p['price']//2);p.setdefault('hotelCost',p['houseCost']);p.setdefault('setMultiplier',2)
    p.setdefault('railroadRents',[25,50,100,200] if p['kind']=='railroad' else [])
    p.setdefault('utilityMultipliers',[4,10] if p['kind']=='utility' else [])

def export_properties(properties):
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=FIELDS);writer.writeheader()
    reverse={v:k for k,v in COLORS.items()}
    for p in properties:
        row=dict(id=p['id'],name=p['name'],kind=p['kind'],group=reverse.get(p['group'],p['group']),purchase_price=p['price'],mortgage_value=p['mortgageValue'])
        # Escape legacy names that could otherwise be interpreted as formulas by spreadsheet apps.
        if row['name'].lstrip().startswith(('=','+','-','@')):row['name']="'"+row['name']
        if p['kind']=='street':row.update(house_cost=p['houseCost'],hotel_cost=p['hotelCost'],set_multiplier=p['setMultiplier'],**dict(zip(FIELDS[9:15],p['rents'])))
        elif p['kind']=='railroad':row.update(dict(zip(FIELDS[15:19],p['railroadRents'])))
        else:row.update(dict(zip(FIELDS[19:21],p['utilityMultipliers'])))
        writer.writerow(row)
    return out.getvalue()
