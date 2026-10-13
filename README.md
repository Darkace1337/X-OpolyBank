# X-opoly

A browser-based bank for your physical property-trading board game. One computer hosts the game, and everyone else joins from a phone, tablet, or computer on the same network.

**This app is a "100% vib-coded mess".** Expect rough edges, keep an eye on the ledger, and report anything that breaks. It's here to make game night easier.

The app handles money, properties, rent, buildings, mortgages, auctions, and trades. You still use your physical board, dice, cards, and pieces to play.

## What you need

- **Host/banker:** a computer with Python 3.10 or newer and the extracted app folder. No additional Python packages are needed.
- **Players:** a modern web browser. No app download, installation, or Python required.
- **Everyone:** access to the same local network. Keep the host computer awake while playing.

## Start the game

Extract the ZIP first. Open the folder containing `server.py`.

### Windows

Double-click `start.bat`, or open a terminal in the app folder and run:

```powershell
py server.py
```

### Linux or macOS

Open a terminal in the app folder and run:

```bash
sh start.sh
```

Or start Python directly:

```bash
python3 server.py
```

Leave the server terminal running. It prints two links:

- **Host/banker link:** open this yourself to get banker controls. Keep the complete link private.
- **Player link:** share this with everyone joining the game.

Players should use the host's network address, such as `http://192.168.1.147:8000/`. That address is only an example; use the one printed by your server. `localhost` on a phone points to the phone, not the host computer.

Click the address under **Invite your players** to display a QR code they can scan.

## Set up your table

1. Open the host/banker link and join with your name and a piece. The banker can also play.
2. Open **House rules → Customize properties → Game variant**, choose your edition, and click **Apply variant**.
3. Set your house rules, including starting cash, GO salary, auction time, and optional Free Parking money.
4. Have the other players open the player link, enter their names, and choose their pieces.
5. Start playing at your physical board and record transactions in the app.

You can switch variants after players join, but only before gameplay starts. Choose the variant before making payments or buying properties. Reset the game to return to setup later.

**Starting cash changes apply to players who join afterward.** They do not change existing balances, including the banker's. Use bank payments to adjust those balances after choosing the variant.

The selected variant's custom pieces appear first, followed by the classic pieces. Each piece can belong to only one player. Tap your name or icon to rename yourself or change your piece.

## Use the app during play

| Tab | What it does |
| --- | --- |
| **Banking** | Send money, pay taxes and fines, pay the $50 jail fee, or declare bankruptcy. Only the banker can award GO money. |
| **Market** | Banker only. Pick an unowned property and the player who landed there, then sell it at face value or start an auction. |
| **Properties** | Shows your properties. Buy or sell houses and hotels, or mortgage and unmortgage deeds. Mortgaged properties appear below the others. |
| **Rent** | Shows other players' properties, grouped by owner. Pay the displayed rent; enter the dice total for utilities. |
| **Trades** | Offer multiple properties and money in either direction. The receiving player accepts or rejects the offer. |
| **House rules** | Banker settings, property customization, and table management. |

Check the ledger when you need to see what happened. Use bank payments for card instructions and corrections.

### Auctions

The banker starts auctions. Players cannot send properties to auction themselves.

Auctions open at **$10**, with bid increases of **$1, $5, $10, $25, and $100**. For an unowned property, everyone may bid, including the banker and the player who landed there. A player selling an owned property cannot bid on their own sale.

- Bids cannot exceed available cash.
- The current highest bidder must wait for someone else to bid before bidding again.
- Every accepted bid restarts the countdown.
- The default timer is **5 seconds**. Set it from **1 to 300 seconds** in House rules before starting an auction.
- The bidder sees an orange flash; other players see a white flash.
- When time runs out, the highest bidder pays and receives the property. With no bids, the property stays with its current owner or the bank.

### Taxes, jail, and bankruptcy

Income Tax is **$200**. Luxury Tax is **$100**, with an alternate name in some variants. You can also pay a custom fixed tax or use the percentage-tax option.

Use **Pay $50 · Get out of jail** to pay your own jail fee to the bank. Move your physical piece and follow your board's remaining jail rules yourself.

Bankruptcy requires confirmation. Your money is cleared, and all your properties return to the bank with mortgages and buildings removed. You stay connected as a spectator. When only one active player remains, the app shows the winner.
Removed sections on variants and publishing from README.
## Close the game

Closing a browser tab does **not** stop the server.

On the host computer:

- **Windows:** double-click `shutdown.bat`, or run `py shutdown.py`.
- **Linux/macOS:** run `sh shutdown.sh`, or `python3 shutdown.py`.
- You can also press **Ctrl+C** in the server terminal.

The shutdown scripts save and stop the game server. They do not turn off the computer.

## Resume, reset, or remove a player

Successful actions automatically save to `game.json`. Start the server again to resume. Use the same browser and network address to retain your player login. Auction clocks keep running in real time; an expired auction settles when the server resumes.

If banker controls are missing, open the complete host/banker link printed in the terminal, or use **Banker access** to restore access.

Under **House rules → Manage table**, the banker can:

- **Kick a player:** disconnect them and return their properties to the bank. They can join again afterward.
- **Reset the game:** type `RESET` to confirm. Other players are disconnected, the banker remains, and balances/ownership are reset. House rules, the selected variant, and customized property names are kept.

To back up a game, stop the server and copy `game.json` somewhere safe. To restore it, stop the server and replace `game.json` with the backup. Keep saves and the `backups` folder private because they contain player sessions and banker access information.

## Add or customize a variant

The app discovers folders inside `Variants`. Each folder needs a `properties.csv`; its folder name becomes the name in the variant selector.

**Space Adventure** is the complete example. Copy its folder, give it a new name, and edit the CSV while keeping the headers and unique property IDs. You can change property names, purchase prices, rent, mortgage values, and building costs.

Optional PNG pieces go directly in the variant folder. Their filenames become the piece names. Use transparent images under 5 MB each, and remove any pieces you don't want. Classic pieces remain available automatically.

Refresh the browser after adding a variant. Select it under **House rules → Customize properties** before gameplay starts. Editing a CSV does not overwrite a game already in progress.

See `PROPERTY-CSV.txt` and `Variants/README.txt` for details. Check `Variants/VERIFICATION-NOTES.txt` for edition-specific limitations; the Star Wars mapping is marked provisional. World Edition is not included.

## If something does not work

- **A phone cannot connect:** check the host's current IP address, confirm the server is running, and make sure both devices are on the same local network. Guest Wi-Fi may block connections between devices. Allow the server through the host firewall on TCP port 8000 if needed.
- **The banker cannot see Market:** use the complete host/banker link, not the ordinary player link.
- **Python is not found:** install Python 3.10 or newer on the host, reopen the terminal, and try again.
- **Port 8000 is already in use:** stop the previous server or use a different port as shown below.
- **A variant will not load:** read its error in the selector and check its CSV against the example.
- **A player lost their login:** first try the original browser and exact URL. If browser data was cleared, the banker may need to remove the old player and help them rejoin.

For a different port or a separate saved game:

```bash
python3 server.py --port 8080 --data friday-game.json
```

Stop that server using the matching settings:

```bash
python3 shutdown.py --port 8080 --data friday-game.json
```

On Windows, replace `python3` with `py`. Share the player URL with the new port number.

When reporting a bug, include what you clicked, what you expected, what happened, and the device/browser you used. Screenshots help; leave out banker links and private save files.
