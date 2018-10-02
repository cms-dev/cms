#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys


def main():
    for line in sys.stdin:
        filename, data = [x.strip() for x in line.split(':')]
        filename = os.path.basename(filename.strip('.'))
        pieces = [x.strip() for x in data.split(',')]
        stats = {'translated': 0, 'untranslated': 0, 'fuzzy': 0}
        for piece in pieces:
            words = piece.split(' ')
            stats[words[1]] = int(words[0])
        print("%s,%d,%d,%d" % (filename,
                               stats['translated'],
                               stats['untranslated'],
                               stats['fuzzy']))

if __name__ == '__main__':
    main()
