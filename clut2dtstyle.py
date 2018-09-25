#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# clut2dtstyle is a Python 3 script to convert Hald CLUTs to darktable
# style files.  It requires darktable-cli, darktable-chart, and
# ImageMagick (for convert and identify).  For more information, run
#
#   clut2dtstyle --help
#

import argparse
import atexit
import numpy as np
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as et


# Minimal darktable sidecar file to convert an image to Lab space.
TO_LAB_XMP = """\
<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:darktable="http://darktable.sf.net/"
    darktable:xmp_version="2">
   <darktable:history>
    <rdf:Seq>
     <rdf:li
      darktable:operation="colorout"
      darktable:enabled="1"
      darktable:modversion="4"
      darktable:params="gz10eJxjY6AfAAAC9AAH"
      darktable:multi_name=""
      darktable:multi_priority="0"
      darktable:blendop_version="7"
      darktable:blendop_params="gz12eJxjYGBgkGAAgRNODESDBnsIHll8ANNSGQM="/>
    </rdf:Seq>
   </darktable:history>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>"""


def main():
    """Argument parsing."""
    arg_parser = argparse.ArgumentParser(prog="clut2dtstyle",
        description="A script to convert Hald CLUTs to darktable styles.")
    arg_parser.add_argument("-n", "--number", default=64, type=int,
        help="""number of input points along an axis used for fitting the CLUT
        and the tone curve""")
    arg_parser.add_argument("-p", "--patches", type=arg_parser_patches,
        default=49, help="""number of patches in the output CLUT (must be an
        integer between 24 and 49)""")
    arg_parser.add_argument("-t", "--title",
        help="title of the generated darktable style")
    arg_parser.add_argument("-o", "--output",
        help="output style file")

    arg_parser.add_argument("file", help="input Hald CLUT")
    args = arg_parser.parse_args()

    try:
        clut_to_dtstyle(args.file, args.output, args.number, args.patches, args.title)
    except PrintError as e:
        print(arg_parser.prog + ": " + str(e), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


class PrintError(Exception):
    pass


def arg_parser_patches(string):
    """Argument parser helper for number of patches."""
    try:
        patches = int(string)
        if patches in range(24, 50):
            return patches
        else:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("patches must be an integer between 24 and 49.")


def remove(name):
    """Remove a file without raising an exception (like rm -rf)."""
    if os.path.exists(name):
        os.remove(name)


def make_temp(extension=".tmp"):
    """Return a temporary file name with the given extension."""
    name = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()) + extension)
    atexit.register(remove, name)
    return name


# Write a temporary file containing the darktable sidecar file.
_to_lab_xmp = make_temp(".xmp")
with open(_to_lab_xmp, "w") as fd:
    fd.write(TO_LAB_XMP)


def get_dimensions(name):
    """Get the dimensions of an image using ImageMagick's identify."""
    try:
        width, height = subprocess.run(["identify", "-format", "%w,%h", name],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL,
                                       encoding="ascii").stdout.split(",")

        width, height = int(width), int(height)

        # For an image to be a valid Hald CLUT file, it must be a square.
        # Additionally, the width must be the cube of a natural number:
        # http://www.quelsolaar.com/technology/clut.html
        if width != height or int(np.cbrt(width)) ** 3 != width:
            raise PrintError("{} has wrong dimensions to be a valid Hald CLUT".format(name))
        else:
            return width, height
    except ValueError:
        raise PrintError("error reading dimesions of {}".format(name))


def lab_array(name, size):
    """Convert an image to a NumPy array (in Lab space)."""
    pfm = make_temp(".pfm")
    subprocess.run(["darktable-cli", name, _to_lab_xmp, pfm],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open(pfm, "rb") as fd:
        # Skip the first three lines containing the header.
        for _ in range(3):
            fd.readline()
        array = np.fromfile(fd, dtype=np.dtype("f4"))

    array = array.reshape((size, size, 3))
    return array[::-1, :, :]


def hald_array(size):
    """Return a neutral Hald CLUT of the given size."""
    name = "hald:{}".format(int(np.cbrt(size)))
    png = make_temp(".png")

    subprocess.run(["convert", name, png],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return lab_array(png, size)


def clut_to_dtstyle(name, output=None, number=64, patches=49, title=None):
    """Convert a Hald CLUT to a darktable style."""
    size = get_dimensions(name)[0]
    hald = hald_array(size)
    array = lab_array(name, size)

    # Determine input/output arrays.
    interval = int(size / number)
    if interval > 1:
        A, B = hald[::interval, ::interval], array[::interval, ::interval]
    else:
        A, B = hald, array

    width = A.shape[0]

    # Choose the stem name of the Hald CLUT file as the style title.
    # This is what shows up in the styles widget in darktable.
    if not title:
        title = os.path.splitext(os.path.basename(name))[0]

    # Directly write the CSV file for extrapolation instead of using
    # a colorchart.  Based on an idea by Heiko Bauke:
    # https://www.mail-archive.com/darktable-dev@lists.darktable.org/msg02441.html
    csv = make_temp(".csv")
    with open(csv, "w") as fd:
        fd.write("name;{}\n".format(title))
        fd.write("description;fitted from Hald CLUT \"{}\" using clut2dstyle\n".format(name))
        fd.write("num_gray;0\n")
        fd.write("patch;L_source;a_source;b_source;L_reference;a_reference;b_reference\n")
        for i in range(width):
            for j in range(width):
                fd.write("A{:02d}B{:02d};{};{};{};{};{};{}\n".format(i, j, *A[i][j], *B[i][j]))

    # Fit the CLUT using darktable-chart.
    if not output:
        output = os.path.splitext(name)[0] + ".dtstyle"
    subprocess.run(["darktable-chart", "--csv", csv, str(patches), output])

    # By default, darktable-chart adds "Input color profile" and "Base curve"
    # operations to the generated dtstyle -- but we don't need them.  Thus,
    # parse the XML tree and remove those operations.
    tree = et.parse(output)
    for style in tree.findall("style"):
        num = 0
        for plugin in style.findall("plugin"):
            if plugin.find("operation").text not in ["colorchecker", "tonecurve"]:
                style.remove(plugin)
            else:
                plugin.find("num").text = str(num)
                num += 1

    tree.write(output)


if __name__ == "__main__":
    sys.exit(main())
