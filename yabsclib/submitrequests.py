#!/usr/bin/python

# Copyright (C) 2008 Dirk Mueller <dmueller@suse.de>

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

from PyQt4 import QtGui, QtCore
from osc import conf, core

class AllSubmitModel(QtCore.QAbstractItemModel):
    """AllSubmitModel()
    
    Model for submit requests
    """
    def __init__(self, parent):
        QtCore.QAbstractItemModel.__init__(self)
        self.workers = []
        self.srs = []
        self.columnmap = ('id', 'state', 'srcproject', 'srcpackage', 'dstproject', 'dstpackage', 'comment')
    
    def setSubmitRequests(self, srs):
        """
        setWorkers(workers)
        
        Set the workers list of the model, as returned from BuildService.getWorkerStatus()
        """
        self.srs = srs
        self.reset()
    
    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data
        """
        try:
            return self.srs[row][self.columnmap[column]]
        except KeyError:
            return ""

    def data(self, index, role):
        """
        data(index, role) -> Qvariant
        
        Returns the QVariant model data located at QModelIndex index
        
        This is normally only called within Qt
        """
        if index.isValid() and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self._data(index.row(), index.column()))
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        """
        headerData(section, orientation, role) -> QVariant
        
        Returns header for section (column) with orientation (Qt.Horizontal or Qt.Vertical)
        
        This is normally only called within Qt
        """
        if role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self.columnmap[section].capitalize())
        else:
            return QtCore.QVariant()

    def index(self, row, column, parent=None):
        """
        index(row, column, parent) -> QModelIndex
        
        Returns a QModelIndex object representing row and column
        """
        return self.createIndex(row, column, id(self._data(row, column)))
        
    def parent(self, index):
        """
        parent(index) -> QModelIndex
        
        Return the parent index of an index (for trees)
        """
        return QtCore.QModelIndex()

    def rowCount(self, parent=None):
        """
        rowCount() -> int
        
        Returns the number of rows of data currently in the model
        """
        return len(self.srs)
        
    def columnCount(self, parent=None):
        """
        columnCount() -> int
        
        Returns the number of columns of data currently in the model
        """
        return len(self.columnmap)

class SubmitRequestThread(QtCore.QThread):
    """
    SubmitRequestThread(bs)
    
    Thread for retrieving worker status. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.workers = []
    
    def run(self):
        self.submitrequests = self.bs.getSubmitRequests()

class SubmitRequestWidget(QtGui.QWidget):
    """
    SubmitRequestWidget(bs, cfg)
    
    Build Service Submit Request viewer widget. bs is a BuildService object and cfg is a ConfigParser object
    """
    def __init__(self, parent, bs, cfg):
        QtGui.QWidget.__init__(self)
        self.viewable = False
        
        self.parent = parent
        
        # BuildService object
        self.bs = bs
        
        # Config object
        self.cfg = cfg

        # 
        
        self.srview = QtGui.QTreeView(self)
        self.srview.setRootIsDecorated(False)
        self.srvmodel = AllSubmitModel(self)
        self.srview.setModel(self.srvmodel)

        # Worker refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.refreshSubmitRequests)
        self.bsthread = SubmitRequestThread(self.bs)
        QtCore.QObject.connect(self.bsthread, QtCore.SIGNAL("finished()"), self.updateSubmitRequestList)

        # Layout
        mainlayout = QtGui.QVBoxLayout()
        mainlayout.addWidget(self.srview)
        self.setLayout(mainlayout)

    def enableRefresh(self, now=False):
        """
        enableRefresh()
        
        Enable widget data refresh
        """
        if now:
            self.refreshSubmitRequests()
        else:
            self.refreshtimer.start(self.cfg.getint('general', 'refreshinterval')*1000)
    
    def disableRefresh(self):
        """
        disableRefresh()
        
        Disable widget data refresh
        """
        self.refreshtimer.stop()

    def setApiurl(self, apiurl):
        """
        setApiurl(apiurl)
        
        Set the buildservice API URL
        """
        self.bs.apiurl = apiurl
        self.refreshSubmitRequests()

    def refreshSubmitRequests(self):
        """
        refreshWorkerLists()
        
        Refresh the worker lists
        """
        self.disableRefresh()
        self.parent.statusBar().showMessage("Retrieving submit requests")
        self.bsthread.start()
    
    def updateSubmitRequestList(self):
        """
        updateSubmitRequestList()
        
        Update worker lists from result in self.bsthread
        """
        if self.viewable:
            self.parent.statusBar().clearMessage()
        submitrequests = self.bsthread.submitrequests
        self.srvmodel.setSubmitRequests(submitrequests)
        for column in range(self.srvmodel.columnCount()):
           self.srview.resizeColumnToContents(column)
        if self.viewable:
            self.enableRefresh()

