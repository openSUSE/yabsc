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

import time
import email.utils
from PyQt4 import QtGui, QtCore

from results import BuildLogThread

#
# Data model
#
class WorkerModel(QtCore.QAbstractItemModel):
    """WorkerModel(bs)
    
    Model for workers. 'bs' must be a BuildService object
    """
    def __init__(self, bs):
        QtCore.QAbstractItemModel.__init__(self)
        self.bs = bs
        self.workers = []
        self.visibleworkers = []
        self.statusfilter = ""
        self.packagefilter = ""
        self.projectfilter = ""
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
        elif role == QtCore.Qt.BackgroundRole:
            worker = self.visibleworkers[index.row()]
            if 'started' in worker:
                # Use the colour scheme from the webclient
                deadline = time.time() - 3600
                starttime = time.mktime(email.utils.parsedate(worker['started']))
                if starttime < deadline:
                    n = (abs((starttime - deadline))/60)
                    if n < 240:
                        return QtCore.QVariant(QtGui.QColor(255, n, 0))

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
        
        if self.packagefilter:
            self.visibleworkers = [w for w in self.visibleworkers if 'package' in w and self.packagefilter in w['package']]
        
        if self.projectfilter:
            if self.projectfilter == 'Watched':
                watchedprojects = self.bs.getWatchedProjectList()
                self.visibleworkers = [w for w in self.visibleworkers if 'project' in w and w['project'] in watchedprojects]
            else:
                self.visibleworkers = [w for w in self.visibleworkers if 'project' in w and w['project'] == self.projectfilter]
    
        if reset:
            self.reset()

    def setStatusFilter(self, status="", reset=True):
        """
        setStatusFilter(status)
        
        Only show workers with a specific status. If status is undefined or
        empty, filter is disabled
        """
        status = status.lower()
        self.statusfilter = status
        self.updateVisibleWorkers()
        
    def setPackageFilter(self, filterstring):
        """
        setPackageFilter(filterstring)
        
        Filter workers building packages containing 'filterstring'
        """
        self.packagefilter = filterstring
        self.updateVisibleWorkers()
        
    def setProjectFilter(self, project):
        """
        setProjectFilter(project)
        
        Filter worker jobs for 'project'. If 'project' is 'All', all projects
        are shown. If 'project' is 'Watched', all watched projects are
        shown
        """
        if project == 'All':
            self.projectfilter = ""
        else:
            self.projectfilter = project
        self.updateVisibleWorkers()

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


class WorkerTreeView(QtGui.QTreeView):
    """
    WorkerTreeView(bs, parent=None)
    
    The worker tree view. 'bs' must be a BuildService object
    """
    def __init__(self, bs, parent=None):
        self.bs = bs
        QtGui.QTreeView.__init__(self, parent)
    
    def contextMenuEvent(self, event):
        """
        contextMenuEvent(event)
        
        Context menu event handler
        """
        index = self.indexAt(event.pos())
        statusindex = self.model().createIndex(index.row(), 2)
        status = str(self.model().data(statusindex, QtCore.Qt.DisplayRole).toString())

        if status == 'building':
            projectindex = self.model().createIndex(index.row(), 3)
            project = str(self.model().data(projectindex, QtCore.Qt.DisplayRole).toString())
            packageindex = self.model().createIndex(index.row(), 4)
            package = str(self.model().data(packageindex, QtCore.Qt.DisplayRole).toString())
            targetindex = self.model().createIndex(index.row(), 5)
            target = str(self.model().data(targetindex, QtCore.Qt.DisplayRole).toString())

            menu = QtGui.QMenu()
            
            abortaction = QtGui.QAction('Abort build', self)
            menu.addAction(abortaction)
            
            selectedaction = menu.exec_(self.mapToGlobal(event.pos()))
            
            if selectedaction:
                try:
                    if selectedaction == abortaction:
                        self.bs.abortBuild(str(project), str(package), str(target))
                except Exception, e:
                    QtGui.QMessageBox.critical(self, "Error",
                               "Could not perform action on project %s: %s" % (project, e))
                    raise


class WorkerWidget(QtGui.QWidget):
    """
    WorkerWidget(bs, cfg)
    
    Build Service worker viewer widget. bs is a BuildService object and cfg is a ConfigParser object
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
        projectlabel = QtGui.QLabel("Target")
        self.projectselector = QtGui.QComboBox()
        self.projectselector.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.projectselector.addItem("All")
        self.projectselector.addItem("Watched")
        QtCore.QObject.connect(self.projectselector, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.filterProjects)

        # Worker tabs
        self.workertab = QtGui.QTabBar()
        QtCore.QObject.connect(self.workertab, QtCore.SIGNAL("currentChanged(int)"), self.filterWorkers)

        self.tabs = []
        for tabname in ('All', 'Building', 'Idle'):
            self.workertab.addTab(tabname)
            self.tabs.append(tabname)
        
        # Status view
        self.workerview = WorkerTreeView(self.bs, parent=self)
        self.workerview.setRootIsDecorated(False)
        self.workermodel = WorkerModel(self.bs)
        self.workerview.setModel(self.workermodel)
        QtCore.QObject.connect(self.workerview, QtCore.SIGNAL("clicked(const QModelIndex&)"), self.watchBuildLog)

        # Build log
        self.logpane = QtGui.QTextBrowser()
        self.logpane.setReadOnly(True)
        self.logpane.setOpenLinks(False)

        # Worker refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.refreshWorkerList)
        self.workerstatusthread = WorkerStatusThread(self.bs)
        QtCore.QObject.connect(self.workerstatusthread, QtCore.SIGNAL("finished()"), self.updateWorkerList)
        
        # Build log refresh
        self.streamtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.streamtimer, QtCore.SIGNAL("timeout()"), self.requestBuildOutput)
        self.buildlogthread = BuildLogThread(self.bs)
        QtCore.QObject.connect(self.buildlogthread, QtCore.SIGNAL("finished()"), self.updateBuildOutput)

        # Layout
        filterlayout = QtGui.QHBoxLayout()
        filterlayout.addWidget(searchlabel)
        filterlayout.addWidget(self.searchedit)
        filterlayout.addWidget(projectlabel)
        filterlayout.addWidget(self.projectselector)
        
        mainlayout = QtGui.QVBoxLayout()
        mainlayout.addLayout(filterlayout)
        mainlayout.addWidget(self.workertab)
        mainlayout.addWidget(self.workerview)
        mainlayout.addWidget(self.logpane)
        self.setLayout(mainlayout)

    def enableRefresh(self, now=False):
        """
        enableRefresh()
        
        Enable widget data refresh
        """
        if now:
            self.refreshWorkerList()
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
        self.refreshWorkerList()

    def refreshWorkerList(self):
        """
        refreshWorkerList()
        
        Refresh the worker lists
        """
        self.disableRefresh()
        self.parent.statusBar().showMessage("Retrieving worker status")
        self.workerstatusthread.start()
    
    def updateWorkerList(self):
        """
        updateWorkerList()
        
        Update worker lists from result in self.workerstatusthread
        """
        if self.viewable:
            self.parent.statusBar().clearMessage()
        workers = self.workerstatusthread.workers
        self.workermodel.setWorkers(workers)
        
        # Update project filter dropbox
        projects = {}
        for worker in workers:
            if 'project' in worker:
                projects[worker['project']] = None
        
        currentprojectfilter = str(self.projectselector.currentText())
        self.projectselector.clear()
        self.projectselector.addItem("All")
        self.projectselector.addItem("Watched")
        self.projectselector.addItems(sorted(projects.keys()))
        if currentprojectfilter in projects.keys() or currentprojectfilter == 'Watched':
            self.projectselector.setCurrentIndex(self.projectselector.findText(currentprojectfilter))
        
        self.resizeColumns()
        self.updateWorkerCounts()
        if self.viewable:
            self.enableRefresh()

    def filterWorkers(self, index):
        """
        filterWorkers(index)
        
        Filter workers by status, specified by tab index
        """
        if self.tabs:
            if index == 0:
                self.workermodel.setStatusFilter()
            else:
                self.workermodel.setStatusFilter(self.tabs[index].lower())
            self.resizeColumns()
            self.updateWorkerCounts()
    
    def filterPackages(self, filterstring):
        """
        filterPackages(filterstring)
        
        Filter worker jobs for packages matching 'filterstring'
        """
        self.workermodel.setPackageFilter(str(filterstring))
    
    def filterProjects(self, project):
        """
        filterProjects(project)
        
        Filter worker jobs for 'project'. If 'project' is 'All', all projects
        are shown. If 'project' is 'Watched', all watched projects are
        shown
        """
        self.workermodel.setProjectFilter(str(project))

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

    def requestBuildOutput(self):
        """
        requestBuildOutput()
        
        Send request to update streaming build output, based on existing buildlogthread parameters
        """
        self.buildlogthread.start()
    
    def updateBuildOutput(self):
        """
        updateBuildOutput()
        
        Update the build output
        """
        if self.viewable:
            self.parent.statusBar().clearMessage()
        self.streamtimer.stop()
        log_chunk = self.buildlogthread.log_chunk
        self.buildlogthread.offset += len(log_chunk)
        self.logpane.append(log_chunk.strip())
        if not len(log_chunk) == 0 and self.viewable:
            self.streamtimer.start(1000)

    def watchBuildLog(self, modelindex):
        """
        watchBuildLog(modelindex)
        
        Watch the build log for the package built by the worker represented by
        QModelIndex modelindex
        """
        # If we're streaming a log file, stop
        self.streamtimer.stop()
        row = modelindex.row()
        self.logpane.clear()
        
        if 'project' in self.workermodel.visibleworkers[row]:
            project = self.workermodel.visibleworkers[row]['project']
            package = self.workermodel.visibleworkers[row]['package']
            target = self.workermodel.visibleworkers[row]['target']

            self.logpane.setCurrentFont(QtGui.QFont("Bitstream Vera Sans Mono", 7))
            self.logpane.setTextColor(QtGui.QColor('black'))
            self.logpane.setWordWrapMode(QtGui.QTextOption.NoWrap)
            
            self.buildlogthread.project = project
            self.buildlogthread.target = target
            self.buildlogthread.package = package
            self.buildlogthread.offset = 0
            self.buildlogthread.live = True

            self.parent.statusBar().showMessage("Retrieving build log for %s" % package)
            self.requestBuildOutput()
