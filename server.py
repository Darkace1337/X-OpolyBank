#!/usr/bin/env python3
"""Local multiplayer X-opoly banker. Python 3.10+, no dependencies."""
import argparse, copy, json, secrets, socket, threading, time, os
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from urllib.parse import unquote, urlsplit
from variants import CLASSIC, LEGACY_PIECES, classic_pieces, discover_variants, get_variant, variant_icon_path
AVATARS=list(CLASSIC)
from property_data import load_properties, parse_properties, export_properties, migrate_property, safe_name
def initial():
    available={v['name']:v for v in discover_variants() if not v['error']}
    default=next((available[name] for name in ('Normal','Classic U.S. Edition') if name in available),None)
    if default is None: raise ValueError('Add a valid Normal or Classic U.S. Edition variant before starting a new game.')
    return dict(players=[],variant=default['name'],variantSettings=copy.deepcopy(default['settings']),properties=default['properties'],trades=[],auction=None,log=[],pot=0,started=False,rules=dict(auctionSeconds=5,startingCash=1500,go=200,landingGoDouble=False,freeParking=False,allowDebt=False,mortgageInterest=10,evenBuilding=True,taxRate=10,taxBase='cash',taxRounding='up'))
class Game:
    def __init__(self,path):
        self.path=Path(path); self.lock=threading.RLock()
        self.bid_condition=threading.Condition(self.lock)
        self.bid_events=deque(maxlen=256); self.bid_sequence=0
        self.data=json.loads(self.path.read_text()) if self.path.exists() else dict(state=initial(),sessions={},hostKey=secrets.token_urlsafe(24))
        self.s['rules'].setdefault('auctionSeconds',5)
        if self.s['auction']: self.s['auction'].setdefault('durationSeconds',5)
        for p in self.s['properties']: migrate_property(p)
        for trade in self.s['trades']:
            for prop in trade.get('fingerprints',{}).values():migrate_property(prop)
        if 'variant' not in self.s:
            themed=any(p.get('avatar') in LEGACY_PIECES for p in self.s['players']) or any("Chococat" in p['name'] or "Hello Kitty" in p['name'] for p in self.s['properties'])
            self.s['variant']='Hello Kitty and Friends' if themed else 'Normal'
            self.s['started']=bool(self.s['started'] or len(self.s['players'])>1 or any(p['owner'] for p in self.s['properties']) or self.s['trades'] or self.s['auction'])
            for p in self.s['players']:
                if p.get('avatar') in LEGACY_PIECES:p['avatar']=f"variant:Hello Kitty and Friends:{LEGACY_PIECES[p['avatar']]}.png"

        if 'variantSettings' not in self.s:
            selected=next((v for v in discover_variants() if v['name']==self.s['variant']),None)
            self.s['variantSettings']=copy.deepcopy(selected['settings']) if selected else {'luxuryTaxName':'Luxury Tax'}
        used={p.get('avatar') for p in self.s['players']}
        for p in self.s['players']:
            if not p.get('avatar'):
                p['avatar']=next(a for a in AVATARS if a not in used); used.add(p['avatar'])
        self.finish_if_last_player()
        self.save()
    @property
    def s(self): return self.data['state']
    def save(self):
        temp=self.path.with_suffix('.tmp'); temp.write_text(json.dumps(self.data)); os.chmod(temp,0o600); temp.replace(self.path)
    def log(self,msg): self.s['log'].insert(0,dict(time=int(time.time()*1000),text=msg)); self.s['log']=self.s['log'][:250]
    def player(self,pid,include_bankrupt=False):
        p=next((p for p in self.s['players'] if p['id']==pid),None)
        if not p: raise ValueError('Player not found.')
        if p.get('bankrupt') and not include_bankrupt: raise ValueError('This player is bankrupt and cannot participate until the game is reset.')
        return p
    def prop(self,pid):
        p=next((p for p in self.s['properties'] if p['id']==pid),None)
        if not p: raise ValueError('Property not found.')
        return p
    def pieces(self):
        selected=next((v for v in discover_variants() if v['name']==self.s['variant']),None)
        return (selected['pieces'] if selected and not selected['error'] else [])+classic_pieces()
    def can_select_variant(self):
        return not self.s['started'] and not self.s.get('gameOver') and not self.s['auction'] and not self.s['trades'] and not any(p['owner'] for p in self.s['properties'])
    def select_variant(self,name):
        if not self.can_select_variant():raise ValueError('Choose the variant before gameplay starts. Reset the game to change it.')
        variant=get_variant(name)
        self.s['variant']=name;self.s['variantSettings']=copy.deepcopy(variant['settings']);self.s['properties']=copy.deepcopy(variant['properties'])
        allowed={p['id'] for p in self.pieces()};used={p['avatar'] for p in self.s['players'] if p['avatar'] in allowed}
        for p in self.s['players']:
            if p['avatar'] not in allowed:p['avatar']=next(a for a in AVATARS if a not in used)
            used.add(p['avatar'])
        self.log(f'Banker selected the {name} variant.')
    def finish_if_last_player(self):
        if self.s.get('gameOver'): return
        players=self.s['players']; active=[p for p in players if not p.get('bankrupt')]
        if len(players)>=2 and len(active)==1 and all(p.get('bankrupt') for p in players if p['id']!=active[0]['id']):
            self.s['gameOver']=dict(winner=active[0]['id'],endedAt=int(time.time()*1000))
            self.s['auction']=None
            for trade in self.s['trades']:
                if trade['status']=='pending': trade['status']='cancelled'
            self.log(f"{active[0]['name']} won the game! All other players are bankrupt.")
    def number(self,v,maximum=10000000):
        if isinstance(v,bool) or not isinstance(v,int) or v<0 or v>maximum: raise ValueError('Enter a valid whole, nonnegative amount.')
        return v
    def debit(self,p,amount):
        reserve=self.s['auction']['bid'] if self.s['auction'] and self.s['auction']['leader']==p['id'] else 0
        if p['cash']-amount<reserve and (reserve or not self.s['rules']['allowDebt']): raise ValueError('Not enough available cash (winning bids are reserved).')
        p['cash']-=amount
    def tick(self):
        a=self.s['auction']
        if a and time.time()*1000>=a['ends']:
            self.s['auction']=None
            prop=self.prop(a['property'])
            if a['leader']:
                winner=self.player(a['leader']); winner['cash']-=a['bid']
                if a['seller']: self.player(a['seller'])['cash']+=a['bid']
                prop['owner']=winner['id']; self.log(f"{winner['name']} won {prop['name']} for ${a['bid']}.")
            else: self.log(f"{prop['name']} auction ended without a bid.")
            self.save()
    def rent_quote(self,p):
        if not p['owner'] or p['mortgaged']:
            return dict(amount=0,multiplier=None,reason='Mortgaged · no rent' if p['mortgaged'] else 'Unowned · no rent')
        group=[x for x in self.s['properties'] if x['group']==p['group']]
        count=sum(x['owner']==p['owner'] for x in group)
        if p['kind']=='utility':
            return dict(amount=None,multiplier=p['utilityMultipliers'][count-1],reason=f"{count} {'utility' if count==1 else 'utilities'} owned")
        if p['kind']=='railroad':
            return dict(amount=p['railroadRents'][count-1],multiplier=None,reason=f"{count} {'railroad' if count==1 else 'railroads'} owned")
        full=p['houses']==0 and count==len(group)
        amount=p['rents'][p['houses']]*(p['setMultiplier'] if full else 1)
        reason='Hotel' if p['houses']==5 else f"{p['houses']} {'house' if p['houses']==1 else 'houses'}" if p['houses'] else f"Complete color group · {p['setMultiplier']}× base rent" if full else 'Base rent'
        return dict(amount=amount,multiplier=None,reason=reason)
    def snapshot(self,token):
        with self.lock:
            self.tick(); session=self.data['sessions'].get(token,{})
            state=copy.deepcopy(self.s)
            for p in state['properties']: p['rentQuote']=self.rent_quote(p)
            return dict(state=state,me=session,serverTime=int(time.time()*1000),pieces=self.pieces(),variants=[dict(name=v['name'],error=v['error']) for v in discover_variants()] if session.get('host') else [],canSelectVariant=self.can_select_variant())
    def action(self,token,d):
        with self.lock:
            if getattr(self,'stopping',False): raise ValueError('The banker is shutting down the server.')
            self.tick(); old=copy.deepcopy(self.data)
            try:
                result=self.apply(token,d)
                if d.get('action') in ['buy','auction','bid','transfer','rent','go','tax','parking','jail','trade','mortgage','build','bankruptcy']:self.s['started']=True
                self.save()
                if d.get('action')=='bid':
                    # Publish only committed bids, using one clock for every browser.
                    a=self.s['auction']; self.bid_sequence+=1
                    self.bid_events.append(dict(sequence=self.bid_sequence,auction=a['id'],
                        bidder=a['leader'],amount=a['bid'],flashAt=int(time.time()*1000)+250))
                    self.bid_condition.notify_all()
                return result
            except Exception:
                self.data=old; raise
    def apply(self,token,d):
        op=d.get('action'); session=self.data['sessions'].get(token,{}); host=session.get('host',False); me=session.get('player')
        if op=='bankerAccess':
            if not secrets.compare_digest(str(d.get('hostKey','')).encode(),self.data['hostKey'].encode()):
                raise ValueError('Invalid banker key. Use the Host / banker link printed by this server.')
            player=self.player(d.get('player') or me,include_bankrupt=True)
            tok=secrets.token_urlsafe(32)
            self.data['sessions'][tok]=dict(player=player['id'],host=True)
            self.log(f'{player["name"]} restored banker access.')
            return dict(token=tok)
        if self.s.get('gameOver') and op not in ['reset','renamePlayer','avatar']:
            raise ValueError('The game is over. The banker can reset the table for a new game.')
        if op=='join':
            name=str(d.get('name','')).strip()[:32]
            if not name: raise ValueError('Enter your name.')
            supplied_key=str(d.get('hostKey',''))
            ishost=secrets.compare_digest(supplied_key.encode(),self.data['hostKey'].encode())
            if supplied_key and not ishost: raise ValueError('Invalid banker key. Use the Host / banker link printed by this server.')
            existing=next((p for p in self.s['players'] if p['name'].lower()==name.lower()),None)
            if existing:
                if not ishost: raise ValueError('That name is already in use. Reconnect with your saved browser session.')
                return self.apply(token,dict(action='bankerAccess',hostKey=supplied_key,player=existing['id']))
            if len(self.s['players'])>=12: raise ValueError('This table is full (12 players).')
            available=[p['id'] for p in self.pieces()]
            avatar=d.get('avatar') or next(a for a in available if all(p.get('avatar')!=a for p in self.s['players']))
            if avatar not in available: raise ValueError('Choose a valid player piece.')
            if any(p.get('avatar')==avatar for p in self.s['players']): raise ValueError('That piece was just taken. Choose another one.')
            pid=secrets.token_hex(6); tok=secrets.token_urlsafe(32)
            self.s['players'].append(dict(id=pid,name=name,cash=self.s['rules']['startingCash'],avatar=avatar))
            self.data['sessions'][tok]=dict(player=pid,host=ishost)
            self.log(f'{name} joined the table.'); return dict(token=tok)
        if not me: raise ValueError('Join the table first.')
        def admin():
            if not host: raise ValueError('Only the host can do that.')
        def owns(pid):
            if pid!=me and not host: raise ValueError('You can only act for your own player.')
        def unlocked(p):
            if self.s['auction'] and self.s['auction']['property']==p['id']: raise ValueError('This property is locked in an auction.')
        def group(p): return [x for x in self.s['properties'] if x['group']==p['group']]
        def tradable(p):
            unlocked(p)
            if any(x['houses'] for x in group(p)): raise ValueError('Sell all buildings in this color group before transferring or mortgaging.')
        if op=='selectVariant':
            admin(); self.select_variant(d.get('variant')); return {}
        if op=='renamePlayer':
            name=str(d.get('name','')).strip()
            if not name or len(name)>32 or any(ord(c)<32 or ord(c)==127 for c in name):
                raise ValueError('Use a player name of 1–32 characters without control characters.')
            if any(p['id']!=me and p['name'].casefold()==name.casefold() for p in self.s['players']):
                raise ValueError('That player name is already in use.')
            player=self.player(me,include_bankrupt=True); old_name=player['name'];player['name']=name
            self.log(f'{old_name} changed their name to {name}.'); return {}
        if op=='jail':
            if d.get('player',me)!=me: raise ValueError('You can only pay your own jail fee.')
            player=self.player(me); self.debit(player,50)
            self.log(f"{player['name']} paid $50 to the bank to get out of jail."); return {}
        if op=='bankruptcy':
            if d.get('player',me)!=me: raise ValueError('Only the player can declare their own bankruptcy.')
            if d.get('confirmation')!='BANKRUPT': raise ValueError('Type BANKRUPT to confirm.')
            target=self.player(me)
            backup_dir=self.path.parent/'backups'; backup_dir.mkdir(exist_ok=True)
            backup=backup_dir/(self.path.stem+'-bankruptcy-'+str(time.time_ns())+'.json')
            with open(backup,'x',opener=lambda path,flags:os.open(path,flags,0o600)) as f: json.dump(self.data,f)
            a=self.s['auction']
            if a and (me in [a.get('seller'),a.get('leader'),a.get('landed')] or self.prop(a['property'])['owner']==me):
                self.s['auction']=None
                self.log('Auction cancelled because a participating player declared bankruptcy.')
            for p in self.s['properties']:
                if p['owner']==me: p.update(owner=None,mortgaged=False,houses=0)
            for t in self.s['trades']:
                if t['status']=='pending' and me in [t['sender'],t['to']]: t['status']='cancelled'
            target.update(cash=0,bankrupt=True)
            self.log(f"{target['name']} declared bankruptcy. All their properties returned to the bank; mortgages and buildings cleared.")
            self.finish_if_last_player()
            return {}
        if op in ['kick','reset']:
            admin()
            if op=='reset':
                if d.get('confirmation')!='RESET': raise ValueError('Type RESET to confirm.')
            else:
                target=self.player(d.get('player'),include_bankrupt=True)
                if any(v.get('host') and v.get('player')==target['id'] for v in self.data['sessions'].values()):
                    raise ValueError('The banker cannot be kicked.')
            # Keep a private recovery copy before either table-management action.
            backup_dir=self.path.parent/'backups'; backup_dir.mkdir(exist_ok=True)
            backup=backup_dir/(self.path.stem+'-'+op+'-'+str(time.time_ns())+'.json')
            with open(backup,'x',opener=lambda path,flags: os.open(path,flags,0o600)) as f:
                json.dump(self.data,f)
            if op=='reset':
                banker=copy.deepcopy(self.player(me,include_bankrupt=True)); banker['cash']=self.s['rules']['startingCash']; banker.pop('bankrupt',None)
                fresh=copy.deepcopy(self.s); fresh.pop('gameOver',None); fresh.update(players=[],trades=[],auction=None,log=[],pot=0,started=False)
                for p in fresh['properties']: p.update(owner=None,mortgaged=False,houses=0)
                fresh['players']=[banker]; self.data['state']=fresh
                self.data['sessions']={token:session}
                self.log('Banker reset the game. Players can join the new table.')
            else:
                pid=target['id']; a=self.s['auction']
                if a and (pid in [a.get('seller'),a.get('leader'),a.get('landed')] or self.prop(a['property'])['owner']==pid):
                    self.s['auction']=None; self.log('Auction cancelled because a participating player was removed.')
                for p in self.s['properties']:
                    if p['owner']==pid: p.update(owner=None,mortgaged=False,houses=0)
                self.s['trades']=[t for t in self.s['trades'] if pid not in [t['sender'],t['to']]]
                self.s['players']=[p for p in self.s['players'] if p['id']!=pid]
                self.data['sessions']={k:v for k,v in self.data['sessions'].items() if v.get('player')!=pid}
                self.log(f"Banker removed {target['name']}; their properties returned to the bank.")
            return {}
        if op=='avatar':
            avatar=d.get('avatar')
            if avatar not in {p['id'] for p in self.pieces()}: raise ValueError('Choose a valid player piece.')
            if any(p['id']!=me and p.get('avatar')==avatar for p in self.s['players']): raise ValueError('That piece is already taken.')
            self.player(me,include_bankrupt=True)['avatar']=avatar; return {}
        if op=='rules':
            admin()
            for k,v in d['rules'].items():
                if k not in self.s['rules']: raise ValueError('Unknown rule.')
                if k in ['landingGoDouble','freeParking','allowDebt','evenBuilding']:
                    if not isinstance(v,bool): raise ValueError('Invalid switch.')
                elif k=='auctionSeconds':
                    if type(v) is not int or not 1<=v<=300: raise ValueError('Auction time must be a whole number from 1 to 300 seconds.')
                elif k=='taxBase':
                    if v not in ['cash','netWorth']: raise ValueError('Invalid tax base.')
                elif k=='taxRounding':
                    if v not in ['up','down']: raise ValueError('Invalid rounding.')
                else: self.number(v,100 if k in ['taxRate','mortgageInterest'] else 1000000)
                self.s['rules'][k]=v
            self.log('Host updated house rules. Starting cash applies to new players.'); return {}
        if op in ['previewProperties','importProperties']:
            admin()
            properties=parse_properties(d.get('csv'))
            if op=='previewProperties': return dict(properties=properties)
            if self.s['auction'] or any(p['owner'] or p['houses'] or p['mortgaged'] for p in self.s['properties']) or any(t['status']=='pending' for t in self.s['trades']):
                raise ValueError('Reset the game before importing a new property sheet. Owned deeds, auctions and pending trades must be cleared first.')
            backup_dir=self.path.parent/'backups'; backup_dir.mkdir(exist_ok=True)
            backup=backup_dir/(self.path.stem+'-properties-'+str(time.time_ns())+'.json')
            with open(backup,'x',opener=lambda path,flags:os.open(path,flags,0o600)) as f:json.dump(self.data,f)
            self.s['properties']=properties;self.s['trades']=[]
            self.log(f"Banker imported a property sheet with {len(properties)} deeds.")
            return {}
        if op=='rename':
            admin(); p=self.prop(d['property']); name=safe_name(d.get('name',''))
            if not name: raise ValueError('Property name cannot be blank.')
            if any(x['id']!=p['id'] and x['name'].casefold()==name.casefold() for x in self.s['properties']): raise ValueError('Another property already has that name.')
            p['name']=name; return {}
        if op=='transfer':
            source=d['from']; target=d['to']; amount=self.number(d['amount'])
            if source==target: raise ValueError('Choose different accounts.')
            if source=='bank': admin()
            else: owns(source); self.debit(self.player(source),amount)
            if target!='bank': self.player(target)['cash']+=amount
            self.log(f"{'Bank' if source=='bank' else self.player(source)['name']} paid ${amount} to {'Bank' if target=='bank' else self.player(target)['name']}."); return {}
        if op in ['go','tax','parking']:
            p=self.player(d.get('player',me)); owns(p['id']); rules=self.s['rules']
            if op=='go':
                admin()
                amount=rules['go']*(2 if d.get('landed') and rules['landingGoDouble'] else 1); p['cash']+=amount; self.log(f"{p['name']} collected ${amount} for GO.")
            elif op=='parking':
                if not rules['freeParking']: raise ValueError('Free Parking jackpot is turned off.')
                amount=self.s['pot']; p['cash']+=amount; self.s['pot']=0; self.log(f"{p['name']} collected ${amount} from Free Parking.")
            else:
                base=p['cash']
                if rules['taxBase']=='netWorth': base+=sum((x['mortgageValue'] if x['mortgaged'] else x['price'])+(4*x['houseCost']+x['hotelCost'] if x['houses']==5 else x['houses']*x['houseCost']) for x in self.s['properties'] if x['owner']==p['id'])
                tax_space={'income':('Income Tax',200),'renovation':(self.s['variantSettings']['luxuryTaxName'],100)}.get(d.get('mode'))
                amount=tax_space[1] if tax_space else self.number(d['amount']) if d.get('mode')=='fixed' else (max(0,base)*rules['taxRate']+(99 if rules['taxRounding']=='up' else 0))//100
                self.debit(p,amount)
                if rules['freeParking']: self.s['pot']+=amount
                self.log(f"{p['name']} paid ${amount} for {tax_space[0] if tax_space else 'tax'}.")
            return {}
        if op in ['buy','mortgage','build','rent','auction']:
            p=self.prop(d['property']); unlocked(p)
            if op=='buy':
                admin()
                buyer=d.get('player'); self.player(buyer)
                if p['owner']: raise ValueError('Property is already owned.')
                self.debit(self.player(buyer),p['price']); p['owner']=buyer; self.log(f"{self.player(buyer)['name']} bought {p['name']}.")
            elif op=='mortgage':
                owns(p['owner']); owner=self.player(p['owner']); tradable(p)
                if p['mortgaged']:
                    cost=(p['mortgageValue']*(100+self.s['rules']['mortgageInterest'])+99)//100; self.debit(owner,cost)
                else: owner['cash']+=p['mortgageValue']
                p['mortgaged']=not p['mortgaged']; self.log(f"{owner['name']} {'mortgaged' if p['mortgaged'] else 'unmortgaged'} {p['name']}.")
            elif op=='build':
                owns(p['owner']); owner=self.player(p['owner']); delta=d['delta']; g=group(p)
                if p['kind']!='street' or delta not in [-1,1]: raise ValueError('Invalid building action.')
                n=p['houses']+delta
                if not 0<=n<=5: raise ValueError('Building limit reached.')
                if delta==1 and any(x['owner']!=p['owner'] or x['mortgaged'] for x in g): raise ValueError('Own the whole unmortgaged color group to build.')
                levels=[n if x['id']==p['id'] else x['houses'] for x in g]
                if self.s['rules']['evenBuilding'] and max(levels)-min(levels)>1: raise ValueError('Build and sell evenly across the group.')
                beforeH=sum(x['houses'] for x in self.s['properties'] if x['houses']<5); beforeT=sum(x['houses']==5 for x in self.s['properties'])
                afterH=beforeH-(p['houses'] if p['houses']<5 else 0)+(n if n<5 else 0); afterT=beforeT-(p['houses']==5)+(n==5)
                if afterH>32 or afterT>12: raise ValueError('Not enough buildings in the bank (32 houses, 12 hotels).')
                cost=p['hotelCost'] if max(n,p['houses'])==5 else p['houseCost']
                if delta==1: self.debit(owner,cost)
                else: owner['cash']+=cost//2
                p['houses']=n; self.log(f"{owner['name']} {'built on' if delta==1 else 'sold a building on'} {p['name']}.")
            elif op=='rent':
                payer=self.player(d.get('player',me)); owns(payer['id'])
                if not p['owner'] or p['owner']==payer['id'] or p['mortgaged']: raise ValueError('No rent is due on this property.')
                quote=self.rent_quote(p); amount=quote['amount']
                if quote['multiplier'] is not None:
                    dice=self.number(d.get('dice'),12)
                    if dice<2: raise ValueError('Enter dice total from 2 to 12.')
                    amount=dice*quote['multiplier']
                if ('expectedAmount' in d and d['expectedAmount']!=amount) or ('expectedOwner' in d and d['expectedOwner']!=p['owner']):
                    raise ValueError('Rent or ownership changed. Review the updated amount and pay again.')
                self.debit(payer,amount); self.player(p['owner'])['cash']+=amount; self.log(f"{payer['name']} paid ${amount} rent for {p['name']}.")
            else:
                if self.s['auction']: raise ValueError('An auction is already running.')
                admin()
                tradable(p)
                if p['mortgaged']: raise ValueError('Unmortgage before auctioning.')
                landed=d.get('player') if not p['owner'] else None
                if landed: self.player(landed)
                self.s['auction']=dict(landed=landed,id=secrets.token_hex(8),property=p['id'],seller=p['owner'],bid=10,leader=None,durationSeconds=self.s['rules']['auctionSeconds'],ends=int(time.time()*1000)+self.s['rules']['auctionSeconds']*1000)
                self.log(f"Auction opened for {p['name']} at $10.")
            return {}
        if op=='bid':
            a=self.s['auction']
            if not a or d.get('auction')!=a['id']: raise ValueError('This auction has ended.')
            if a['seller']==me: raise ValueError('The seller cannot bid.')
            if a['leader']==me: raise ValueError('You are the highest bidder. Wait until someone else bids.')
            inc=self.number(d.get('increment'),100)
            if inc not in [0,1,5,10,25,100] or (inc==0 and a['leader']): raise ValueError('Choose a valid bid increment.')
            amount=a['bid']+inc
            if self.player(me)['cash']<amount: raise ValueError('Not enough cash to bid.')
            a.update(bid=amount,leader=me,ends=int(time.time()*1000)+a['durationSeconds']*1000); return {}
        if op=='trade':
            other=d['to']; self.player(other)
            if other==me: raise ValueError('Choose another player.')
            give=list(dict.fromkeys(d.get('give',[]))); take=list(dict.fromkeys(d.get('take',[])))
            giveCash=self.number(d.get('giveCash',0)); takeCash=self.number(d.get('takeCash',0))
            if not give and not take and not giveCash and not takeCash: raise ValueError('Add money or properties to the offer.')
            fingerprints={}
            for ids,owner in [(give,me),(take,other)]:
                for pid in ids:
                    p=self.prop(pid); tradable(p)
                    if p['owner']!=owner: raise ValueError('Property ownership changed.')
                    fingerprints[pid]=copy.deepcopy(p)
            self.s['trades'].insert(0,dict(id=secrets.token_hex(8),sender=me,to=other,give=give,take=take,giveCash=giveCash,takeCash=takeCash,fingerprints=fingerprints,status='pending'))
            self.log(f"{self.player(me)['name']} offered a trade to {self.player(other)['name']}."); return {}
        if op=='tradeResponse':
            t=next((t for t in self.s['trades'] if t['id']==d['trade']),None)
            if not t or t['status']!='pending': raise ValueError('This trade is no longer available.')
            decision=d['decision']
            if decision=='cancel' and me==t['sender']: t['status']='cancelled'; return {}
            if me!=t['to'] or decision not in ['accept','reject']: raise ValueError('Only the recipient can accept or reject.')
            if decision=='reject': t['status']='rejected'; return {}
            for pid,fp in t['fingerprints'].items():
                p=self.prop(pid); tradable(p)
                if p!=fp: raise ValueError('A property changed since this offer. Reject it and request a new offer.')
            a=self.player(t['sender']); b=self.player(t['to'])
            # Validate both gross payments before either credit; rollback guarantees atomicity.
            self.debit(a,t['giveCash']); self.debit(b,t['takeCash']); a['cash']+=t['takeCash']; b['cash']+=t['giveCash']
            for ids,owner in [(t['give'],b['id']),(t['take'],a['id'])]:
                for pid in ids: self.prop(pid)['owner']=owner
            t['status']='accepted'; self.log(f"{a['name']} and {b['name']} completed a trade."); return {}
        raise ValueError('Unknown action.')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def respond(self,code,data,ctype='application/json'):
        body=json.dumps(data).encode() if ctype=='application/json' else data
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def bid_stream(self):
        game=self.server.game
        with game.lock:
            try: cursor=int(self.headers.get('Last-Event-ID',game.bid_sequence))
            except ValueError: cursor=game.bid_sequence
            if cursor<0 or cursor>game.bid_sequence: cursor=game.bid_sequence
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Accel-Buffering','no')
        self.end_headers()
        self.connection.settimeout(20)
        try:
            self.wfile.write(f'id: {cursor}\nevent: ready\ndata: {{}}\n\n'.encode()); self.wfile.flush()
            while not getattr(game,'stopping',False):
                with game.bid_condition:
                    game.bid_condition.wait_for(lambda: game.bid_sequence>cursor or getattr(game,'stopping',False),timeout=10)
                    events=[event for event in game.bid_events if event['sequence']>cursor]
                for event in events:
                    self.wfile.write(f"id: {event['sequence']}\nevent: bid\ndata: {json.dumps(event)}\n\n".encode())
                    cursor=event['sequence']
                if not events: self.wfile.write(b': heartbeat\n\n')
                self.wfile.flush()
        except (OSError,TimeoutError): pass
        self.close_connection=True
    def do_GET(self):
        if self.path=='/api/bid-events': return self.bid_stream()
        if self.path.split('?')[0]=='/api/state':
            snapshot=self.server.game.snapshot(self.headers.get('Authorization','').removeprefix('Bearer '))
            snapshot['joinUrl']=getattr(self.server,'join_url',None)
            return self.respond(200,snapshot)
        if self.path=='/api/properties.csv':
            token=self.headers.get('Authorization','').removeprefix('Bearer ')
            with self.server.game.lock:
                if not self.server.game.data['sessions'].get(token,{}).get('host'): return self.respond(403,{'error':'Only the banker can export properties.'})
                content=export_properties(self.server.game.s['properties']).encode('utf-8-sig')
            return self.respond(200,content,'text/csv; charset=utf-8')
        file={'/':'index.html','/app.js':'app.js','/qrcode.js':'qrcode.js','/bid-flash.js':'bid-flash.js','/style.css':'style.css'}.get(self.path.split('?')[0])
        if urlsplit(self.path).path.startswith('/variant-icons/'):
            parts=urlsplit(self.path).path.split('/')
            try:
                if len(parts)!=4:raise ValueError('Icon not found.')
                asset=variant_icon_path(unquote(parts[2]),unquote(parts[3]))
                return self.respond(200,asset.read_bytes(),'image/png')
            except (ValueError,OSError):return self.respond(404,{'error':'Icon not found.'})
        if self.path.startswith('/icons/') and self.path[7:] in [a+'.svg' for a in AVATARS]:
            return self.respond(200,(ROOT/'public/icons'/self.path[7:]).read_bytes(),'image/svg+xml')
        if not file: return self.respond(404,{'error':'Not found'})
        self.respond(200,(ROOT/'public'/file).read_bytes(),{'index.html':'text/html; charset=utf-8','app.js':'application/javascript','qrcode.js':'application/javascript','bid-flash.js':'application/javascript','style.css':'text/css'}[file])
    def do_POST(self):
        if self.path=='/api/shutdown':
            key=self.headers.get('Authorization','').removeprefix('Bearer ')
            if self.client_address[0] not in ['127.0.0.1','::1'] or self.headers.get('Origin') or not secrets.compare_digest(key.encode(),self.server.game.data['hostKey'].encode()):
                return self.respond(403,{'error':'Local banker shutdown credentials required.'})
            try:
                with self.server.game.lock:
                    self.server.game.save()
                    self.server.game.stopping=True
                self.respond(200,{'message':'Game saved. Server shutting down.'})
            finally:
                if getattr(self.server.game,'stopping',False):
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
            return
        if self.path!='/api/action': return self.respond(404,{'error':'Not found'})
        origin=self.headers.get('Origin')
        if origin and origin not in ['http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')]: return self.respond(403,{'error':'Origin rejected'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if length>131072: raise ValueError('Request too large.')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('JSON required.')
            d=json.loads(self.rfile.read(length))
            self.respond(200,self.server.game.action(self.headers.get('Authorization','').removeprefix('Bearer '),d))
        except (ValueError,KeyError,TypeError) as e: self.respond(400,{'error':str(e)})
        except Exception: self.respond(500,{'error':'Could not save the action. Please try again.'})
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8000); parser.add_argument('--bind',default='0.0.0.0'); parser.add_argument('--data',default=str(ROOT/'game.json')); args=parser.parse_args()
    game=Game(args.data); server=ThreadingHTTPServer((args.bind,args.port),Handler); server.game=game
    print(f'Host / banker: http://localhost:{args.port}/#host={game.data["hostKey"]}',flush=True)
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('192.0.2.1',80)); ip=s.getsockname()[0]; s.close()
    except OSError: ip='<your-computer-IP>'
    server.join_url=f'http://{ip}:{args.port}' if ip!='<your-computer-IP>' else None
    print(f'Players on your Wi-Fi: http://{ip}:{args.port}',flush=True)
    stopped=threading.Event()
    def clock():
        while not stopped.wait(.05):
            with game.lock:
                if not getattr(game,'stopping',False): game.tick()
    threading.Thread(target=clock,daemon=True).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        stopped.set()
        with game.lock:
            game.stopping=True
            game.save()
        server.server_close()
        print('Game saved. X-opoly server stopped.',flush=True)
if __name__=='__main__': main()
