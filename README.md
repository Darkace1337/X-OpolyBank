# X-opoly

A local-network banking companion for a physical property-trading board game.
The host runs Python 3.10 or newer; players join through their browsers.

Run `python3 server.py` (Windows: `py server.py`) and open the host URL printed
in the terminal. Share only the player URL. See START.txt for full instructions.

## Variants

Themed property names are included. Sanrio artwork and reference images
are excluded. Space Adventure includes 28 original fictional property names
and seven black-and-white character icons as a complete example. Classic pieces remain available in every variant. You can add
optional PNG pieces locally; see Variants/README.txt.

## Publishing

This folder contains the application source and runtime files. Development
tests, saved games, session keys, backups, and Sanrio artwork are not included.
Publish this folder, not the parent workspace or your private game folder.
Never commit a custom save file; it can contain player sessions and host access.

Select and add your code license before publishing. Existing third-party
notices are in ICON-CREDITS.txt and QRCODE-LICENSE.txt and must be retained.
Property and character names are not a grant of trademark rights. This project
is not affiliated with or endorsed by Hasbro or Sanrio.
