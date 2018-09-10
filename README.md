clut2dtstyle
============

clut2dtstyle is a Python script to convert color lookup tables (CLUTs)
in the form of [Hald CLUTs][1] (used by RawTherapee, digiKam, etc.) to
a [darktable][1] compatible style file.  It requires `darktable-chart`
from darktable and ImageMagick (for `convert` and `identify`).

Usage
-----

Since darktable only supports CLUTs with at most 49 patches, the
conversion will be approximate (but reasonable).  Although Hald CLUTs
are usually distributed as PNGs, clut2dtstyle will also work with CLUTs
in other lossless formats.

### Existing Hald CLUT

If you already have a Hald CLUT you want to convert to a darktable style
file, you can use clut2dtstyle directly (with additional options):

```bash
clut2dtstyle                               \
  --number 50                              \
  --output film_emulation_preset-1.dtstyle \
  --patches 40                             \
  --title 'Film Emulation Preset 1'        \
  film_emulation_preset-1.png
```

Note that using a large number of sampling points results in a large
computation time.  Since darktable-chart does not support more that 49
patches in the output CLUT, doing this will not result in a better fit.

### Cloning a filter

If you wish to "clone" a certain filter or style (e.g., one applied by
an external program), use ImageMagick to generate a neutral Hald CLUT
first:

```bash
convert hald:4 hald4.png
# apply external filter on hald4.png and save to output.png
clut2dtstyle output.png
```

If the program applying the filter produces only lossy output (e.g., as
a JPEG file), it is better to scale up the neutral Hald CLUT before
applying the filter:

```bash
convert hald:4 -scale 1080x1080 hald4.png
# apply external filter on hald4.png and save to output.jpg
convert -scale 64x64 output.jpg output.png
clut2dtstyle output.png
```

Again, since the number of patches in the output CLUT is limited, it
does not make much sense to go beyond a level-4 CLUT for cloning
a filter.

License
-------

Public domain.  See the file UNLICENSE for more details.

[1]: http://www.quelsolaar.com/technology/clut.html
[2]: https://www.darktable.org/
