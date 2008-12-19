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

class SubmitRequestModel(QtCore.QAbstractItemModel):
    """SubmitRequestModel(bs)
    
    Model for submit requests. 'bs' must be a BuildService object
    """
    def __init__(self, bs):
        QtCore.QAbstractItemModel.__init__(self)
        self.bs = bs
        self.submitrequests = []
        self.visiblesubmitrequests = []
        self.statefilter = ""
        self.packagefilter = ""
        self.srcprojectfilter = ""
        self.dstprojectfilter = ""
        self.columnmap = ('id', 'state', 'srcproject', 'srcpackage', 'dstproject', 'dstpackage', 'comment')
    
    def setSubmitRequests(self, submitrequests):
        """
        setSubmitRequests(workers)
        
        Set the submitrequests list of the model, as returned from BuildService.getSubmitRequests()
        """
        self.submitrequests = submitrequests
        self.updateVisibleSubmitrequests()
    
    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data
        """
        try:
            return self.visiblesubmitrequests[row][self.columnmap[column]]
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
        return len(self.visiblesubmitrequests)
        
    def columnCount(self, parent=None):
        """
        columnCount() -> int
        
        Returns the number of columns of data currently in the model
        """
        return len(self.columnmap)

    def updateVisibleSubmitrequests(self, reset=True):
        """
        updateVisibleSubmitrequests(reset=True)
        
        Update the list of visible submitrequests
        """
        self.visiblesubmitrequests = self.submitrequests
        
        if self.statefilter:
            self.visiblesubmitrequests = [s for s in self.visiblesubmitrequests if s['state'] == self.statefilter]
        
        if self.packagefilter:
            self.visiblesubmitrequests = [s for s in self.visiblesubmitrequests if (self.packagefilter in s['srcpackage'] or self.packagefilter in s['dstpackage'])]
        
        if 'Watched' in (self.srcprojectfilter, self.dstprojectfilter):
            watchedprojects = self.bs.getWatchedProjectList()

        for (filter, key) in ((self.srcprojectfilter, 'srcproject'), (self.dstprojectfilter, 'dstproject')):
            if filter:
                if filter == 'Watched':
                    self.visiblesubmitrequests = [s for s in self.visiblesubmitrequests if s[key] in watchedprojects]
                else:
                    self.visiblesubmitrequests = [s for s in self.visiblesubmitrequests if s[key] == filter]

        if reset:
            self.reset()

    def setStateFilter(self, state="", reset=True):
        """
        setStateFilter(state, reset=True)
        
        Only show submitrequests with a specific state. If status is undefined
        or empty, filter is disabled
        """
        state = state.lower()
        self.statefilter = state
        self.updateVisibleSubmitrequests()
        
    def setPackageFilter(self, filterstring):
        """
        setPackageFilter(filterstring)
        
        Filter submitrequests for packages containing 'filterstring'
        """
        self.packagefilter = filterstring
        self.updateVisibleSubmitrequests()
        
    def setSourceProjectFilter(self, project):
        """
        setSourceProjectFilter(project)
        
        Filter submitrequests for mathing source projects. If 'project' is
        'All', all projects are shown. If 'project' is 'Watched', all watched
        projects are shown
        """
        if project == 'All':
            self.srcprojectfilter = ""
        else:
            self.srcprojectfilter = project
        self.updateVisibleSubmitrequests()

    def setDestinationProjectFilter(self, project):
        """
        setDestinationProjectFilter(project)
        
        Filter submitrequests for mathing destination projects. If 'project' is
        'All', all projects are shown. If 'project' is 'Watched', all watched
        projects are shown
        """
        if project == 'All':
            self.dstprojectfilter = ""
        else:
            self.dstprojectfilter = project
        self.updateVisibleSubmitrequests()

    def numRequestsWithState(self, state):
        """
        numRequestsWithState(state)
        
        Return the number of submitreqs with state
        """
        state = state.lower()
        if state == 'all':
            return len(self.submitrequests)
        return len([s for s in self.submitrequests if s['state'] == state])

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

        # Filter widgets
        searchlabel = QtGui.QLabel("Search")
        self.searchedit = QtGui.QLineEdit()
        QtCore.QObject.connect(self.searchedit, QtCore.SIGNAL("textChanged(const QString&)"), self.filterPackages)
        srcprojectlabel = QtGui.QLabel("Source Project")
        self.srcprojectselector = QtGui.QComboBox()
        self.srcprojectselector.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.srcprojectselector.addItem("All")
        self.srcprojectselector.addItem("Watched")
        QtCore.QObject.connect(self.srcprojectselector, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.filterSourceProjects)
        dstprojectlabel = QtGui.QLabel("Destination Project")
        self.dstprojectselector = QtGui.QComboBox()
        self.dstprojectselector.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.dstprojectselector.addItem("All")
        self.dstprojectselector.addItem("Watched")
        QtCore.QObject.connect(self.dstprojectselector, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.filterDestinationProjects)

        # State tabs
        self.statetab = QtGui.QTabBar()
        QtCore.QObject.connect(self.statetab, QtCore.SIGNAL("currentChanged(int)"), self.filterState)

        self.tabs = []
        for tabname in ('All', 'New', 'Rejected', 'Accepted', 'Declined', 'Revoked', 'Deleted'):
            self.statetab.addTab(tabname)
            self.tabs.append(tabname)

        # Main view
        self.srview = QtGui.QTreeView(self)
        self.srview.setRootIsDecorated(False)
        self.srvmodel = SubmitRequestModel(self.bs)
        self.srview.setModel(self.srvmodel)

        # Data refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.refreshSubmitRequests)
        self.bsthread = SubmitRequestThread(self.bs)
        QtCore.QObject.connect(self.bsthread, QtCore.SIGNAL("finished()"), self.updateSubmitRequestList)

        # Layout
        filterlayout = QtGui.QHBoxLayout()
        filterlayout.addWidget(searchlabel)
        filterlayout.addWidget(self.searchedit)
        filterlayout.addWidget(srcprojectlabel)
        filterlayout.addWidget(self.srcprojectselector)
        filterlayout.addWidget(dstprojectlabel)
        filterlayout.addWidget(self.dstprojectselector)

        mainlayout = QtGui.QVBoxLayout()
        mainlayout.addLayout(filterlayout)
        mainlayout.addWidget(self.statetab)
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

        # Update project filter dropboxes
        srcprojects = {}
        dstprojects = {}
        for submitrequest in submitrequests:
            srcprojects[submitrequest['srcproject']] = None
            dstprojects[submitrequest['dstproject']] = None
        
        for (selector, projects) in ((self.srcprojectselector, srcprojects), (self.dstprojectselector, dstprojects)):
            currentfilter = str(selector.currentText())
            selector.clear()
            selector.addItem("All")
            selector.addItem("Watched")
            selector.addItems(sorted(projects.keys()))
            if currentfilter in projects.keys() or currentfilter == 'Watched':
                selector.setCurrentIndex(selector.findText(currentfilter))

        self.resizeColumns()
        self.updateStateCounts()
        if self.viewable:
            self.enableRefresh()

    def resizeColumns(self):
        """
        resizeColumns()
        
        Resize columns to fit contents
        """
        for column in range(self.srvmodel.columnCount()):
           self.srview.resizeColumnToContents(column)        

    def updateStateCounts(self):
        """
        updateStateCounts()
        
        Update counts for state tabs
        """
        for tab in self.tabs:
            self.statetab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab, self.srvmodel.numRequestsWithState(tab)))

    def filterState(self, index):
        """
        filterState(index)
        
        Filter submitreqs by state, specified by tab index
        """
        if self.tabs:
            if index == 0:
                self.srvmodel.setStateFilter()
            else:
                self.srvmodel.setStateFilter(self.tabs[index].lower())
            self.resizeColumns()
            self.updateStateCounts()

    def filterPackages(self, filterstring):
        """
        filterPackages(filterstring)
        
        Filter submitrequests for packages matching 'filterstring'
        """
        self.srvmodel.setPackageFilter(str(filterstring))
    
    def filterSourceProjects(self, project):
        """
        filterSourceProjects(project)
        
        Filter submitreqs for 'project'. If 'project' is 'All', all projects
        are shown. If 'project' is 'Watched', all watched projects are
        shown
        """
        self.srvmodel.setSourceProjectFilter(str(project))

    def filterDestinationProjects(self, project):
        """
        filterDestinationProjects(project)
        
        Filter submitreqs for 'project'. If 'project' is 'All', all projects
        are shown. If 'project' is 'Watched', all watched projects are
        shown
        """
        self.srvmodel.setDestinationProjectFilter(str(project))
