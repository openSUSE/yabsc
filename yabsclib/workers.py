#
# workers.py - Worker status widget for Yabsc
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

from PyQt4 import QtGui, QtCore

from results import BuildLogThread

#
# Data model
#
class WorkerModel(QtCore.QAbstractItemModel):
    """WorkerModel()
    
    Model for workers
    """
    def __init__(self):
        QtCore.QAbstractItemModel.__init__(self)
        self.workers = []
        self.visibleworkers = []
        self.statusfilter = ""
        self.columnmap = ('id', 'hostarch', 'status', 'project', 'package', 'target', 'started')
    
    def setWorkers(self, workers):
        """
        setWorkers(workers)
        
        Set the workers list of the model, as returned from BuildService.getWorkerStatus()
        """
        self.workers = workers
        self.updateVisibleWorkers()
    
    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data
        """
        try:
            return self.visibleworkers[row][self.columnmap[column]]
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
        return len(self.visibleworkers)
        
    def columnCount(self, parent=None):
        """
        columnCount() -> int
        
        Returns the number of columns of data currently in the model
        """
        return len(self.columnmap)

    def updateVisibleWorkers(self, reset=True):
        """
        updateVisibleWorkers(reset=True)
        
        Update the list of visible workers
        """
        self.visibleworkers = self.workers
        
        if self.statusfilter:
            self.visibleworkers = [w for w in self.visibleworkers if w['status'] == self.statusfilter]
        
        if reset:
            self.reset()

    def setStatusFilter(self, status="", reset=True):
        """
        setStatusFilter(status)
        
        Only show workers with a specific status. If status is undefined or
        empty, filter is disabled
        """
        self.statusfilter = status
        if status == "All":
            self.visibleworkers = self.workers
        else:
            self.visibleworkers = [w for w in self.workers if w['status'] == status]
        self.reset()

    def numWorkersWithStatus(self, status):
        """
        numWorkersWithStatus(status)
        
        Return the number of workers with status
        """
        status = status.lower()
        if status == 'all':
            return len(self.workers)
        return len([w for w in self.workers if w['status'] == status])


#
# API call threads
#
class WorkerStatusThread(QtCore.QThread):
    """
    WorkerStatusThread(bs)
    
    Thread for retrieving worker status. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.workers = []
    
    def run(self):
        self.workers = self.bs.getWorkerStatus()


class WorkerWidget(QtGui.QWidget):
    """
    WorkerWidget(bs, cfg)
    
    Build Service worker viewer widget. bs is a BuildService object and cfg is a ConfigParser object
    """
    def __init__(self, bs, cfg):
        QtGui.QWidget.__init__(self)
        self.viewable = False
        
        # BuildService object
        self.bs = bs
        
        # Config object
        self.cfg = cfg
        
        # Worker tabs
        self.workertab = QtGui.QTabBar()

        self.tabs = []
        for tabname in ('All', 'Building', 'Idle'):
            self.workertab.addTab(tabname)
            self.tabs.append(tabname)
        
        self.workerview = QtGui.QTreeView()
        self.workerview.setRootIsDecorated(False)
        self.workermodel = WorkerModel()
        self.workerview.setModel(self.workermodel)

        # Worker refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.refreshWorkerLists)
        self.workerstatusthread = WorkerStatusThread(self.bs)
        QtCore.QObject.connect(self.workerstatusthread, QtCore.SIGNAL("finished()"), self.updateWorkerLists)

        # Layout
        mainlayout = QtGui.QVBoxLayout()
        mainlayout.addWidget(self.workertab)
        mainlayout.addWidget(self.workerview)
        self.setLayout(mainlayout)

    def enableRefresh(self):
        """
        enableRefresh()
        
        Enable widget data refresh
        """
        self.refreshtimer.start(10000)
    
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
        self.refreshWorkerLists()

    def refreshWorkerLists(self):
        """
        refreshWorkerLists()
        
        Refresh the worker lists
        """
        self.disableRefresh()
        self.workerstatusthread.start()
    
    def updateWorkerLists(self):
        """
        updateWorkerLists()
        
        Update worker lists from result in self.workerstatusthread
        """
        workers = self.workerstatusthread.workers
        self.workermodel.setWorkers(workers)
        self.resizeColumns()
        self.updateWorkerCounts()
        if self.viewable:
            self.enableRefresh()

    def resizeColumns(self):
        """
        resizeColumns()
        
        Resize columns to fit contents
        """
        for column in range(self.workermodel.columnCount()):
            self.workerview.resizeColumnToContents(column)

    def updateWorkerCounts(self):
        """
        updateWorkerCounts()
        
        Update counts for worker tabs
        """
        for tab in self.tabs:
            self.workertab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab, self.workermodel.numWorkersWithStatus(tab)))
