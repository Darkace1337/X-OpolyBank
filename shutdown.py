#!/usr/bin/env python3
"""Stop this X-opoly server locally, without shutting down the computer."""
import argparse,json,sys,urllib.request,urllib.error
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--data',default=str(Path(__file__).resolve().parent/'game.json'),help='Use the same saved-game file passed to server.py.')
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Port must be between 1 and 65535.')
    try:
        data=json.loads(Path(args.data).read_text());key=data['hostKey']
        req=urllib.request.Request(f'http://127.0.0.1:{args.port}/api/shutdown',data=b'{}',headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req,timeout=10) as response:
            print(json.load(response)['message'])
        print('Your computer remains on. Restart the game with start.sh or start.bat.')
        return 0
    except urllib.error.HTTPError as e:
        if e.code==404:print('This server predates the shutdown script. Stop it with Ctrl+C, then start it once using the updated server.py.',file=sys.stderr)
        elif e.code==403:print('Shutdown refused. Check that --data points to the running server\'s saved game.',file=sys.stderr)
        else:print(f'Server returned HTTP {e.code}; shutdown was not confirmed.',file=sys.stderr)
    except urllib.error.URLError:
        print('Cannot reach the server. It may already be stopped; check --port.',file=sys.stderr)
    except (OSError,ValueError,KeyError,TypeError):
        print('Could not read the saved game or confirm shutdown. Check --data and try again.',file=sys.stderr)
    return 1
if __name__=='__main__':sys.exit(main())
