#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# clut2dtstyle is a Python script to convert Hald CLUTs into
# darktable-compatible style files using darktable-chart.
#

import argparse
import numpy as np
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as et

# Regex to extract Lab values from ImageMagick's tex:- output.
LAB_TEX_RE = re.compile(r"^.*cielab\(([^%]+)%,([^%]+)%,([^%]+)%\)$")


def main():
    """Argument parsing."""
    arg_parser = argparse.ArgumentParser(prog="clut2dtstyle",
        description="A script to convert Hald CLUTs to darktable dtstyles.")
    arg_parser.add_argument("-n", "--number", default=64, type=int,
        help="""number of input points along an axis used for fitting
        the color chart and the tone curve""")
    arg_parser.add_argument("-p", "--patches", type=arg_parser_patches,
        default=49, help="""number of patches in the output color chart (must
        be an integer between 24 and 49)""")
    arg_parser.add_argument("-t", "--title",
        help="title of the generated darktable style")
    arg_parser.add_argument("-o", "--output",
        help="output file")

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
    """Argument parser for number of patches."""
    try:
        patches = int(string)
        if patches in range(24, 50):
            return patches
        else:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("patches must be an integer between 24 and 49.")


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
    try:
        stdout = subprocess.run(["convert", name, "-colorspace", "Lab", "txt:-"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                encoding='ascii').stdout.split("\n")

        array = np.empty((size * size, 3))
        for i, line in enumerate(stdout[1:-1]):
            array[i] = LAB_TEX_RE.match(line).groups()
    except AttributeError:
        raise PrintError("error converting {} into a Lab array".format(name))

    return array.reshape((size, size, 3))


def clut_to_dtstyle(name, output=None, number=64, patches=49, title=None):
    size = get_dimensions(name)[0]
    hald = lab_array("hald:{}".format(np.cbrt(size)), size)
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
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", encoding="ascii") as csv:
        csv.write("name; {}\n".format(title))
        csv.write("description;fitted from Hald CLUT \"{}\" using clut2dstyle\n".format(name))
        csv.write("num_gray;0\n")
        csv.write("patch;L_source;a_source;b_source;L_reference;a_reference;b_reference\n")
        for i in range(width):
            for j in range(width):
                csv.write("A{:02d}B{:02d};{};{};{};{};{};{}\n".format(i, j, *A[i][j], *B[i][j]))

        # Fit the CLUT using darktable-chart.
        if not output:
            output = os.path.splitext(name)[0] + ".dtstyle"
        subprocess.run(["darktable-chart", "--csv", csv.name, str(patches), output])

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
