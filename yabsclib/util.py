#
# util.py - Utility functions for Yabsc
#

# Copyright (C) 2008 James Oakley <jfunk@opensuse.org>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

from PyQt4 import QtCore

def checkState2bool(checkstate):
    """
    checkState2bool(checkstate) -> bool
    
    Convert a Qt.CheckState to bool. Ignores tristate
    """
    return bool(checkstate)

def bool2checkState(b):
    """
    bool2checkState(b) -> Qt.CheckState
    
    Convert a bool to Qt.CheckState. Ignores tristate
    """
    if b:
        return QtCore.Qt.Checked
    else:
        return QtCore.Qt.Unchecked

