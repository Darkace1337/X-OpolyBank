X-opoly variants

Create a subfolder named exactly as you want it to appear in House rules > Customize properties.
Copy Normal/properties.csv into it and edit the names, prices, and rents.
Keep the CSV headers and unique property IDs.

Put optional PNG icons directly in that folder (maximum 5 MB per icon).
The file name without .png is the label shown in the piece picker.
Classic SVG pieces are always included from public/icons.

Example:
  Variants/Space Adventure/properties.csv
  Variants/Space Adventure/Moon Pilot.png

Refresh the app to discover your folder automatically. Only the banker
can apply a variant, including after players join, before game actions begin.

Optional settings.json can rename the fixed $100 tax space:
  {"luxuryTaxName":"Renovation"}
Without this file it is called Luxury Tax. Income Tax remains $200.

Files in nested reference/ folders are not loaded as player icons.
CSV values are copied into the game save when the variant is applied.
Editing source CSVs does not change an ongoing game.

Space Adventure is a complete example with 28 fictional property names and
seven original PNG pieces. Copy its folder to start making your own variant.

ADDITIONAL INCLUDED EDITIONS
Australian Edition (1990)
Classic German Edition
Classic UK Edition
Classique - French Edition
Marvel - French Edition (2014)
Star Wars - Collectors Edition (1996) [Provisional]
The Simpsons Edition (2001)

See VERIFICATION-NOTES.txt for checks, corrections and limitations.
