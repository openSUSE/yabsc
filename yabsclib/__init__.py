#
# yabsc - Yet Another Build Service Client
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

import asyncore
import base64
import ConfigParser
import httplib
import os
import select
import sys
import time
import urllib2
import urlparse
import xml.etree.cElementTree as ElementTree
from PyQt4 import QtGui, QtCore
from osc import conf, core
import SubmitRequestWidget

defaultconfig = {'general': {'autoscroll': False},
                 'persistence': {'size': '900,725'}}

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


class BuildService(QtCore.QObject):
    "Interface to Build Service API"
    def __init__(self, apiurl=None):
        QtCore.QObject.__init__(self)

        conf.get_config()
        if apiurl:
            self.apiurl = apiurl
        else:
            self.apiurl = conf.config['apiurl']
        
    def getAPIServerList(self):
        """getAPIServerList() -> list
        
        Get list of API servers configured in .oscrc
        """
        apiservers = []
        for host in conf.config['auth_dict'].keys():
            apiurl = "%s://%s" % (conf.config['scheme'], host)
        return apiservers
    
    def getUserName(self):
        """getUserName() -> str
        
        Get the user name associated with the current API server
        """
        hostname = urlparse.urlparse(self.apiurl)[1]
        return conf.config['auth_dict'][hostname]['user']
    
    def getProjectList(self):
        """getProjectList() -> list
        
        Get list of projects
        """
        return [project for project in core.meta_get_project_list(self.apiurl) if project != 'deleted']
    
    def getWatchedProjectList(self):
        """getWatchedProjectList() -> list
        
        Get list of watched projects
        """
        username = self.getUserName()
        tree = ElementTree.fromstring(''.join(core.get_user_meta(self.apiurl, username)))
        projects = []
        watchlist = tree.find('watchlist')
        if watchlist:
            for project in watchlist.findall('project'):
                projects.append(project.get('name'))
        homeproject = 'home:%s' % username
        if not homeproject in projects and homeproject in self.getProjectList():
            projects.append(homeproject)
        return projects

    def getResults(self, project):
        """getResults(project) -> (dict, list)
        
        Get results of a project. Returns (results, targets)
        
        results is a dict, with package names as the keys, and lists of result codes as the values
        
        targets is a list of targets, corresponding to the result code lists
        """
        results = {}
        targets = []
        tree = ElementTree.fromstring(''.join(core.show_prj_results_meta(self.apiurl, project)))
        for result in tree.findall('result'):
            targets.append('/'.join((result.get('repository'), result.get('arch'))))
            for status in result.findall('status'):
                package = status.get('package')
                code = status.get('code')
                if not package in results:
                    results[package] = []
                results[package].append(code)
        return (results, targets)

    def getTargets(self, project):
        """
        getTargets(project) -> list
        
        Get a list of targets for a project
        """
        targets = []
        tree = ElementTree.fromstring(''.join(core.show_project_meta(self.apiurl, project)))
        for repo in tree.findall('repository'):
            for arch in repo.findall('arch'):
                targets.append('%s/%s' % (repo.get('name'), arch.text))
        return targets

    def getPackageStatus(self, project, package):
        """
        getPackageStatus(project, package) -> dict
        
        Returns the status of a package as a dict with targets as the keys and status codes as the
        values
        """
        status = {}
        tree = ElementTree.fromstring(''.join(core.show_results_meta(self.apiurl, project, package)))
        for result in tree.findall('result'):
            target = '/'.join((result.get('repository'), result.get('arch')))
            statusnode = result.find('status')
            code = statusnode.get('code')
            details = statusnode.find('details')
            if details is not None:
                code += ': ' + details.text
            status[target] = code
        return status
    
    def getBinaryList(self, project, target, package):
        """
        getBinaryList(project, target, package) -> list
        
        Returns a list of binaries for a particular target and package
        """
        (repo, arch) = target.split('/')
        core.get_binarylist(self.apiurl, project, repo, arch, package)
        
    def getBuildLog(self, project, target, package, offset=0):
        """
        getBuildLog(project, target, package, offset=0) -> str
        
        Returns the build log of a package for a particular target.
        
        If offset is greater than 0, return only text after that offset. This allows live streaming
        """
        (repo, arch) = target.split('/')
        return core.get_buildlog(self.apiurl, project, package, repo, arch, offset)
    
    def getWorkerStatus(self):
        """
        getWorkerStatus() -> list of dicts
        
        Get worker status as a list of dictionaries. Each dictionary contains the keys 'id',
        'hostarch', and 'status'. If the worker is building, the dict will additionally contain the
        keys 'project', 'package', 'target', and 'starttime'
        """
        url = core.makeurl(self.apiurl, ['build', '_workerstatus'])
        f = core.http_GET(url)
        tree = ElementTree.parse(f).getroot()
        workerstatus = []
        for worker in tree.findall('building'):
            d = {'id': worker.get('workerid'),
                 'status': 'building'}
            for attr in ('hostarch', 'project', 'package', 'starttime'):
                d[attr] = worker.get(attr)
            d['target'] = '/'.join((worker.get('repository'), worker.get('arch')))
            d['started'] = time.asctime(time.localtime(float(worker.get('starttime'))))
            workerstatus.append(d)
        for worker in tree.findall('idle'):
            d = {'id': worker.get('workerid'),
                 'hostarch': worker.get('hostarch'),
                 'status': 'idle'}
            workerstatus.append(d)
        return workerstatus

    def getSubmitRequests(self):
        """
        getSubmitRequests() -> list of dicts
        
        """
        url = core.makeurl(self.apiurl, ['search', 'request', '?match=submit'])
        f = core.http_GET(url)
        tree = ElementTree.parse(f).getroot()
        submitrequests = []
        for sr in tree.findall('request'):
            if sr.get('type') != "submit":
                continue

            d = {'id': sr.get('id')}
            sb = sr.findall('submit')[0]
            src = sb.findall('source')[0]
            d['srcproject'] = src.get('project')
            d['srcpackage'] = src.get('package')
            dst = sb.findall('target')[0]
            d['dstproject'] = dst.get('project')
            d['dstpackage'] = dst.get('package')
            d['state'] = sr.findall('state')[0].get('name')

            submitrequests.append(d)
        return submitrequests



#
# Data models
#

class AllResultModel(QtCore.QAbstractItemModel):
    """AllResultModel()
    
    Model for package results
    """
    def __init__(self):
        QtCore.QAbstractItemModel.__init__(self)
        self.results = []
        self.targets = []
        self.targetfilter = "All"
        self.visibletargets = []
        self.packages = []
        self.packagefilter = ""
        self.visiblepackages = []
    
    def setResults(self, results, targets):
        """
        setResults(results, targets)
        
        Set the results dict and targets list of the model, as returned from
        BuildService.getResults()
        """
        self.results = results
        self.targets = targets
        self.packages = sorted(results.keys())
        self.setPackageFilter(self.packagefilter, reset=False)
        self.setTargetFilter(self.targetfilter, reset=False)
        self.reset()
    
    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data. The 0th column is the package name, and subsequent
        columns are result codes
        """
        package = self.visiblepackages[row]
        if column == 0:
            return package
        else:
            return self.results[package][column-1]
    
    def packageFromRow(self, row):
        """
        packageFromRow(row) -> str
        
        Get the package name associated with a row
        """
        return self._data(row, 0)

    def data(self, index, role):
        """
        data(index, role) -> Qvariant
        
        Returns the QVariant model data located at QModelIndex index
        
        This is normally only called within Qt
        """
        if not index.isValid():
             return QtCore.QVariant()
        txt = self._data(index.row(), index.column())
        if role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(txt)
        elif role == QtCore.Qt.ForegroundRole:
            if txt in ("succeeded",):
                return QtCore.QVariant(QtGui.QColor(QtCore.Qt.green))
            if txt in ("building",):
                return QtCore.QVariant(QtGui.QColor(QtCore.Qt.blue))
            if txt in ("disabled",):
                return QtCore.QVariant(QtGui.QColor(QtCore.Qt.gray))
            if txt in ("expansion error", "failed", "broken"):
                return QtCore.QVariant(QtGui.QColor(QtCore.Qt.red))
        elif role == QtCore.Qt.BackgroundRole:
            if txt in ("building", "scheduled"):
                return QtCore.QVariant(QtGui.QColor(QtCore.Qt.gray))

        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        """
        headerData(section, orientation, role) -> QVariant
        
        Returns header for section (column) with orientation (Qt.Horizontal or Qt.Vertical)
        
        This is normally only called within Qt
        """
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return QtCore.QVariant("Package")
            else:
                return QtCore.QVariant(self.visibletargets[section-1])
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
        return len(self.visiblepackages)
        
    def columnCount(self, parent=None):
        """
        columnCount() -> int
        
        Returns the number of columns of data currently in the model
        """
        return len(self.visibletargets) + 1
    
    def setPackageFilter(self, filterstring, reset=True):
        """
        setPackageFilter(filterstring)
        
        Only show packages matching filterstring
        """
        self.packagefilter = filterstring
        if filterstring:
            self.visiblepackages = [p for p in self.packages if filterstring in p]
        else:
            self.visiblepackages = self.packages
        if reset:
            self.reset()

    def setTargetFilter(self, target, reset=True):
        """
        setTargetFilter(target)
        
        Only show target
        """
        self.targetfilter = target
        if target == "All":
            self.visibletargets = self.targets
        else:
            self.visibletargets = [t for t in self.targets if t == target]
        if reset:
            self.reset()


class FilteredResultModel(AllResultModel):
    """
    FilteredResultModel(status)
    
    Model for package results that match a particular status
    """
    def __init__(self, status):
        AllResultModel.__init__(self)
        self.status = status

    def setResults(self, results, targets):
        """
        setResults(results, targets)
        
        Set the results dict and targets list of the model, as returned from
        BuildService.getResults()
        """
        self.results = results
        self.targets = targets
        self.packages = sorted(filter(lambda p: self.status in self.results[p], results.keys()))
        self.setPackageFilter(self.packagefilter, reset=False)
        self.setTargetFilter(self.targetfilter, reset=False)
        self.reset()
    
    def getMatchingPackageTargets(self, package):
        """
        getMatchingPackageTargets(package) -> list
        
        Get a list of targets of a package whose code matches the model's status filter
        """
        targets = []
        for (i, target) in enumerate(self.visibletargets):
            if self.results[package][i] == self.status:
                targets.append(target)
        return targets

    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data. The 0th column is the package name, and the 1st
        column is a comma-separated list of package targets whose code matches the model's status
        filter
        """
        package = self.visiblepackages[row]
        if column == 0:
            return package
        else:
            return ', '.join(self.getMatchingPackageTargets(package))

    def headerData(self, section, orientation, role):
        """
        headerData(section, orientation, role) -> QVariant
        
        Returns header for section (column) with orientation (Qt.Horizontal or Qt.Vertical)
        
        This is normally only called within Qt
        """
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return QtCore.QVariant("Package")
            else:
                return QtCore.QVariant("Targets")
        else:
            return QtCore.QVariant()

    def columnCount(self, parent=None):
        """
        columnCount() -> int
        
        Returns the number of columns of data in this model (always 2 here)
        """
        return 2

    def setPackageFilter(self, filterstring, reset=True, updatetargetfilter=True):
        """
        setPackageFilter(filterstring)
        
        Only show packages matching filterstring
        """
        AllResultModel.setPackageFilter(self, filterstring, reset=False)
        if updatetargetfilter:
            self.setTargetFilter(self.targetfilter, reset)

    def setTargetFilter(self, target, reset=True):
        """
        setTargetFilter(target)
        
        Only show target
        """
        AllResultModel.setTargetFilter(self, target, reset=False)
        if self.targetfilter != "All":
            self.visiblepackages = [p for p in self.visiblepackages if self.getMatchingPackageTargets(p)]
        else:
            self.setPackageFilter(self.packagefilter, reset=False, updatetargetfilter=False)
        if reset:
            self.reset()


class AllWorkerModel(QtCore.QAbstractItemModel):
    """AllWorkerModel()
    
    Model for workers
    """
    def __init__(self):
        QtCore.QAbstractItemModel.__init__(self)
        self.workers = []
        self.columnmap = ('id', 'hostarch', 'status', 'project', 'package', 'target', 'started')
    
    def setWorkers(self, workers):
        """
        setWorkers(workers)
        
        Set the workers list of the model, as returned from BuildService.getWorkerStatus()
        """
        self.workers = workers
        self.reset()
    
    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data
        """
        try:
            return self.workers[row][self.columnmap[column]]
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
        return len(self.workers)
        
    def columnCount(self, parent=None):
        """
        columnCount() -> int
        
        Returns the number of columns of data currently in the model
        """
        return len(self.columnmap)


class FilteredWorkerModel(AllWorkerModel):
    """
    FilteredWorkerModel(status)
    
    Model for workers that match a particular status
    """
    def __init__(self, status):
        AllWorkerModel.__init__(self)
        self.status = status

    def setWorkers(self, workers):
        """
        setWorkers(workers)
        
        Set the workers list of the model, as returned from BuildService.getWorkerStatus()
        """
        self.workers = [w for w in workers if w['status'] == self.status]
        self.reset()


#
# API call threads
#
class ProjectListThread(QtCore.QThread):
    """
    ProjectListThread(bs)
    
    Thread for retrieving project lists. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.projects = []
        self.watched = True
    
    def run(self):
        if self.watched:
            self.projects = self.bs.getWatchedProjectList()
        else:
            self.projects = self.bs.getProjectList()

class ProjectResultsThread(QtCore.QThread):
    """
    ProjectResultsThread(bs)
    
    Thread for retrieving project results. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.project = None
        self.results = []
        self.targets = []
    
    def run(self):
        (self.results, self.targets) = self.bs.getResults(self.project)

class PackageStatusThread(QtCore.QThread):
    """
    PackageStatusThread(bs)
    
    Thread for retrieving package status. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.project = None
        self.package = None
        self.status = {}
    
    def run(self):
        self.status = self.bs.getPackageStatus(self.project, self.package)

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

class BuildLogThread(QtCore.QThread):
    """
    BuildLogThread(bs)
    
    Thread for retrieving build logs. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.project = None
        self.target = None
        self.package = None
        self.offset = 0
        self.live = False
        self.log_chunk = ""
    
    def run(self):
        self.log_chunk = self.bs.getBuildLog(self.project, self.target, self.package, self.offset)

#
# Main widget
#
class BSWidget(QtGui.QWidget):
    """
    BSWidget(bs, cfg)
    
    Build Service status viewer widget. bs is a BuildService object and cfg is a ConfigParser object
    """
    def __init__(self, bs, cfg):
        QtGui.QWidget.__init__(self)
        self.viewable = False
        
        # BuildService object
        self.bs = bs
        
        # Config object
        self.cfg = cfg
        
        # Convenience attributes
        self.currentproject = ''
        self.initialprojectrefresh = True
        
        # Project list selector
        self.projectlistselector = QtGui.QComboBox()
        self.projectlistselector.addItem("Watched Projects")
        self.projectlistselector.addItem("All Projects")
        if self.cfg.has_option('persistence', 'projectlist'):
            self.projectlistselector.setCurrentIndex(self.cfg.getint('persistence', 'projectlist'))
        QtCore.QObject.connect(self.projectlistselector, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.refreshProjectList)

        # The project list
        self.projecttreeview = QtGui.QTreeView()
        self.projecttreeview.setRootIsDecorated(False)
        self.projectlistmodel = QtGui.QStandardItemModel(0, 1, self)
        self.projectlistmodel.setHeaderData(0, QtCore.Qt.Horizontal, QtCore.QVariant("Project"))
        self.projectlistthread = ProjectListThread(self.bs)
        self.refreshProjectList()
        self.projecttreeview.setModel(self.projectlistmodel)
        QtCore.QObject.connect(self.projecttreeview, QtCore.SIGNAL("clicked(const QModelIndex&)"), self.projectSelected)
        QtCore.QObject.connect(self.projectlistthread, QtCore.SIGNAL("finished()"), self.updateProjectList)
        
        # Filter widgets
        searchlabel = QtGui.QLabel("Search")
        self.searchedit = QtGui.QLineEdit()
        QtCore.QObject.connect(self.searchedit, QtCore.SIGNAL("textChanged(const QString&)"), self.filterPackages)
        targetlabel = QtGui.QLabel("Target")
        self.targetselector = QtGui.QComboBox()
        self.targetselector.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.targetselector.addItem("All")
        QtCore.QObject.connect(self.targetselector, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.filterTarget)

        # Project results
        self.projecttab = QtGui.QTabWidget()

        self.tabs = []
        
        for tabname in ('All', 'Succeeded', 'Failed', 'Building', 'Blocked', 'Scheduled', 'Expansion Error', 'Broken', 'Disabled'):
            tab = {'name': tabname}
            tab['view'] = QtGui.QTreeView()
            tab['view'].setRootIsDecorated(False)
            if tabname == 'All':
                tab['model'] = AllResultModel()
            else:
                tab['model'] = FilteredResultModel(tabname.lower())
            tab['view'].setModel(tab['model'])
            self.projecttab.addTab(tab['view'], tabname)
            QtCore.QObject.connect(tab['view'], QtCore.SIGNAL("clicked(const QModelIndex&)"), self.refreshPackageInfo)
            self.tabs.append(tab)

        # Result refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.timerRefresh)
        self.projectresultsthread = ProjectResultsThread(self.bs)
        QtCore.QObject.connect(self.projectresultsthread, QtCore.SIGNAL("finished()"), self.updatePackageLists)

        # Package info
        self.packageinfo = QtGui.QTextBrowser()
        self.packageinfo.setReadOnly(True)
        self.packageinfo.setOpenLinks(False)
        QtCore.QObject.connect(self.packageinfo, QtCore.SIGNAL("anchorClicked(const QUrl&)"), self.viewBuildOutput)
        self.packagestatusthread = PackageStatusThread(self.bs)
        QtCore.QObject.connect(self.packagestatusthread, QtCore.SIGNAL("finished()"), self.updatePackageInfo)

        # Stream parameters and timer
        self.streamtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.streamtimer, QtCore.SIGNAL("timeout()"), self.requestBuildOutput)
        self.buildlogthread = BuildLogThread(self.bs)
        QtCore.QObject.connect(self.buildlogthread, QtCore.SIGNAL("finished()"), self.updateBuildOutput)

        # Layout
        projectlistlayout = QtGui.QVBoxLayout()
        projectlistlayout.addWidget(self.projectlistselector)
        projectlistlayout.addWidget(self.projecttreeview)
        filterlayout = QtGui.QHBoxLayout()
        filterlayout.addWidget(searchlabel)
        filterlayout.addWidget(self.searchedit)
        filterlayout.addWidget(targetlabel)
        filterlayout.addWidget(self.targetselector)
        packagelistlayout = QtGui.QVBoxLayout()
        packagelistlayout.addLayout(filterlayout)
        packagelistlayout.addWidget(self.projecttab)
        packagelistlayout.addWidget(self.packageinfo)
        mainlayout = QtGui.QHBoxLayout()
        mainlayout.addLayout(projectlistlayout)
        mainlayout.addLayout(packagelistlayout, 1)
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
    
    #
    # Slots
    #
    def setApiurl(self, apiurl):
        """
        setApiurl(apiurl)
        
        Set the buildservice API URL
        """
        self.bs.apiurl = apiurl
        self.currentproject = ""
        self.refreshProjectList()

    def refreshProjectList(self, dummy=None):
        """
        refreshProjectList(dummy=None)
        
        Refresh the project list from the current buildservice API
        """
        if str(self.projectlistselector.currentText()) == "Watched Projects":
            self.projectlistthread.watched = True
        else:
            self.projectlistthread.watched = False
        self.projectlistthread.start()
    
    def updateProjectList(self):
        """
        updateProjectList()
        
        Update project list from result in self.projectlistthread
        """
        self.projectlistmodel.clear()
        for project in sorted(self.projectlistthread.projects):
            si = QtGui.QStandardItem(project)
            si.setEditable(False)
            self.projectlistmodel.appendRow(si)
        self.projectlistmodel.setHeaderData(0, QtCore.Qt.Horizontal, QtCore.QVariant("Project"))
        self.projecttreeview.sortByColumn(0, QtCore.Qt.AscendingOrder)
        if self.initialprojectrefresh:
            self.initialprojectrefresh = False
            if self.cfg.has_option('persistence', 'project'):
                lastproject = self.cfg.get('persistence', 'project')
                if lastproject in self.projectlistthread.projects:
                    self.currentproject = lastproject
                    self.targetselector.clear()
                    self.targetselector.addItem("All")
                    self.targetselector.addItems(self.bs.getTargets(lastproject))
                    self.refreshPackageLists(lastproject)

    def refreshPackageLists(self, project):
        """
        refreshPackageLists(project)
        
        Refresh the package lists to show results for the specified project
        """
        self.disableRefresh()
        self.projectresultsthread.project = project
        self.projectresultsthread.start()

    def updatePackageLists(self):
        """
        updatePackageLists()
        
        Update package list data from result in self.projectresultsthread
        """
        results = self.projectresultsthread.results
        targets = self.projectresultsthread.targets
        for tab in self.tabs:
            tab['model'].setResults(results, targets)
            for column in range(tab['model'].columnCount()):
                tab['view'].resizeColumnToContents(column)
            self.projecttab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab['name'], tab['model'].rowCount()))
        if self.viewable:
            self.enableRefresh()

    def projectSelected(self, modelindex):
        """
        projectSelected(self, modelindex)
        
        Set the current project to that represented by QModelIndex modelindex and refresh the
        package lists
        """
        self.currentproject = str(self.projectlistmodel.data(modelindex, QtCore.Qt.DisplayRole).toString())
        self.targetselector.clear()
        self.targetselector.addItem("All")
        self.targetselector.addItems(self.bs.getTargets(self.currentproject))
        self.refreshPackageLists(self.currentproject)
    
    def timerRefresh(self):
        """
        timerRefresh()
        
        Refresh the package lists from a timer signal
        """
        if self.currentproject:
            self.refreshPackageLists(self.currentproject)

    def refreshPackageInfo(self, modelindex):
        """
        refreshPackageInfo(modelindex)
        
        Refresh the package info for the package represented by QModelIndex modelindex
        """
        # If we're streaming a log file, stop
        self.streamtimer.stop()
        tab = self.tabs[self.projecttab.currentIndex()]
        model = tab['model']
        tabname = tab['name']
        column = modelindex.column()
        row = modelindex.row()
        package = model.packageFromRow(row)
        if tabname == 'All':
            if column > 0:
                statuscode = model._data(row, column)
                if statuscode in ("succeeded", "building", "failed"):
                    target = model.targets[column-1]
                    self.viewBuildOutput(QtCore.QUrl('%s,%s' % (target, package)))
                    return
        self.packagestatusthread.project = self.currentproject
        self.packagestatusthread.package = package
        self.packagestatusthread.start()
        
    def updatePackageInfo(self):
        """
        updatePackageInfo()
        
        Update the pkginfo pane to the result from self.packagestatusthread
        """
        package = self.packagestatusthread.package
        pitext = "<h2>%s</h2>" % package
        # Results
        #pitext += "<h3>Results:</h3><table>"
        pitext += "<table>"
        status = self.packagestatusthread.status
        for target in status.keys():
            statustext = status[target]
            code = statustext.split(':')[0]
            if code == "succeeded":
                color = "green"
            elif code == "building":
                color = "blue"
            elif code == "disabled":
                color = "gray"
            elif code in ('failed', 'expansion error'):
                color = "red"
            else:
                color = "black"
            pitext += "<tr><td><b>%s</b></td><td><font color='%s'><b>" % (target, color)
            if code in ('succeeded', 'building', 'failed'):
                pitext += "<a href='%s,%s'>%s</a>" % (target, package, statustext)
            else:
                pitext += statustext
            pitext += "</b></font></td></tr>"
        pitext += "</table>"
#        binaries = self.bs.getBinaryList(self.currentproject, target, package)
#        if binaries:
#            pitext += "<b>Binaries:</b><br/>"
#            for binary in binaries:
#                pitext += "%s<br/>" % binary

        self.packageinfo.setWordWrapMode(QtGui.QTextOption.WordWrap)
        self.packageinfo.setText(pitext)
    
    def viewBuildOutput(self, arg):
        """
        viewBuildOutput(arg)
        
        Show build output for the "target/package" specified in arg. If the package is currently
        building, stream the output until it is finished
        """
        (target, package) = str(arg.toString()).split(',')
        self.packageinfo.clear()
        # For some reason, the font is set to whatever the calling link had. Argh
        self.packageinfo.setCurrentFont(QtGui.QFont("Bitstream Vera Sans Mono", 7))
        self.packageinfo.setTextColor(QtGui.QColor('black'))
        self.packageinfo.setWordWrapMode(QtGui.QTextOption.NoWrap)
        
        self.buildlogthread.project = self.currentproject
        self.buildlogthread.target = target
        self.buildlogthread.package = package
        self.buildlogthread.offset = 0

        if self.bs.getPackageStatus(self.currentproject, package)[target].startswith('building'):
            self.buildlogthread.live = True
        else:
            self.buildlogthread.live = False
        self.requestBuildOutput()
    
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
        self.streamtimer.stop()
        if self.buildlogthread.live:
            log_chunk = self.buildlogthread.log_chunk
            self.buildlogthread.offset += len(log_chunk)
            self.packageinfo.append(log_chunk.strip())
            if not len(log_chunk) == 0 and self.viewable:
                self.streamtimer.start(1000)
        else:
            self.packageinfo.setPlainText(self.buildlogthread.log_chunk)
            if self.cfg.getboolean('general', 'autoscroll'):
                self.packageinfo.moveCursor(QtGui.QTextCursor.End)
    
    def filterPackages(self, filterstring):
        """
        filterPackages(filterstring)
        
        Show only packages that match filterstring
        """
        for tab in self.tabs:
            tab['model'].setPackageFilter(str(filterstring))
            for column in range(tab['model'].columnCount()):
                tab['view'].resizeColumnToContents(column)
            self.projecttab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab['name'], tab['model'].rowCount()))
        
        
    def filterTarget(self, target):
        for tab in self.tabs:
            tab['model'].setTargetFilter(str(target))
            for column in range(tab['model'].columnCount()):
                tab['view'].resizeColumnToContents(column)
            self.projecttab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab['name'], tab['model'].rowCount()))


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
        self.workertab = QtGui.QTabWidget()

        self.tabs = []
        
        for tabname in ('All', 'Building', 'Idle'):
            tab = {'name': tabname}
            tab['view'] = QtGui.QTreeView()
            tab['view'].setRootIsDecorated(False)
            if tabname == 'All':
                tab['model'] = AllWorkerModel()
            else:
                tab['model'] = FilteredWorkerModel(tabname.lower())
            tab['view'].setModel(tab['model'])
            self.workertab.addTab(tab['view'], tabname)
            self.tabs.append(tab)

        # Worker refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.refreshWorkerLists)
        self.workerstatusthread = WorkerStatusThread(self.bs)
        QtCore.QObject.connect(self.workerstatusthread, QtCore.SIGNAL("finished()"), self.updateWorkerLists)

        # Layout
        mainlayout = QtGui.QVBoxLayout()
        mainlayout.addWidget(self.workertab)
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
        for tab in self.tabs:
            tab['model'].setWorkers(workers)
            for column in range(tab['model'].columnCount()):
                tab['view'].resizeColumnToContents(column)
            self.workertab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab['name'], tab['model'].rowCount()))
        if self.viewable:
            self.enableRefresh()


class ApiSelection:
    """
    ApiSelection(apiurl, bsw, ww)
    
    Allows the selection of an apiurl for BSWidget bsw and WorkerWidget ww
    """
    def __init__(self, apiurl, bsw, ww):
       self.apiurl = apiurl
       self.bsw = bsw
       self.ww = ww
       
    def selected(self):
        """
        selected(self)
        
        Set apiurl of the BSWidget to that represented by this object
        """
        self.bsw.setApiurl(self.apiurl)
        self.ww.setApiurl(self.apiurl)

class ConfigureDialog(QtGui.QDialog):
    """
    ConfigureDialog()
    
    Yabsc configuration dialog
    """
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        
        self.setWindowTitle("Yabsc Configuration")
        
        self.autoscrollcheckbox = QtGui.QCheckBox("Automatically scroll to the bottom of finished build logs")
        
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.autoscrollcheckbox)
        
        buttonlayout = QtGui.QHBoxLayout()
        buttonlayout.addStretch(1)
        ok = QtGui.QPushButton('Ok')
        self.connect(ok, QtCore.SIGNAL('clicked()'), self.accept)
        buttonlayout.addWidget(ok)
        cancel = QtGui.QPushButton('Cancel')
        self.connect(cancel, QtCore.SIGNAL('clicked()'), self.reject)
        buttonlayout.addWidget(cancel)
        
        layout.addLayout(buttonlayout)
        
        self.setLayout(layout)


class ExportDialog(QtGui.QDialog):
    """
    ExportDialog()
    
    Yabsc export dialog
    """
    def __init__(self, model, parent=None):
        QtGui.QDialog.__init__(self, parent)

        self.setWindowTitle("Yabsc Export")

        layout = QtGui.QVBoxLayout()

        self.headers = []
        for i in xrange(model.columnCount()):
            name = str(model.headerData(i, 0, QtCore.Qt.DisplayRole).toString())
            checkbox = QtGui.QCheckBox('Include column "%s"' % name)
            checkbox.setCheckState(bool2checkState(True))
            self.headers.append({'name': name, 'index': i, 'checkbox': checkbox})

            layout.addWidget(checkbox)
        
        seplayout = QtGui.QHBoxLayout()
        seplabel = QtGui.QLabel('Separator')
        seplayout.addWidget(seplabel)
        self.sepcombo = QtGui.QComboBox()
        self.sepcombo.addItems(['Tab', 'Comma', 'Space'])
        self.separatormap = {'Tab': '\t',
                             'Comma': ',',
                             'Space': ' '}
        seplayout.addWidget(self.sepcombo)
        layout.addLayout(seplayout)
        
        buttonlayout = QtGui.QHBoxLayout()
        buttonlayout.addStretch(1)
        ok = QtGui.QPushButton('Ok')
        self.connect(ok, QtCore.SIGNAL('clicked()'), self.accept)
        buttonlayout.addWidget(ok)
        cancel = QtGui.QPushButton('Cancel')
        self.connect(cancel, QtCore.SIGNAL('clicked()'), self.reject)
        buttonlayout.addWidget(cancel)
        
        layout.addLayout(buttonlayout)
        
        self.setLayout(layout)


class MainWindow(QtGui.QMainWindow):
    """
    MainWindow()
    
    YABSC main window widget
    """
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        
        # Configuration
        self.cfgfilename = os.path.expanduser('~/.yabscrc')
        self.cfg = ConfigParser.ConfigParser()

        if os.path.exists(self.cfgfilename):
            try:
                f = open(self.cfgfilename)
                self.cfg.readfp(f)
                f.close()
            except IOError, e:
                QtGui.QMessageBox.critical(self, "Configuration File Error",
                                           "Could not read configuration file %s: %s" % (self.cfgfilename, e))
        
        # Set configuration defaults
        for section in defaultconfig:
            if not self.cfg.has_section(section):
                self.cfg.add_section(section)
            for (key, val) in defaultconfig[section].items():
                if not self.cfg.has_option(section, key):
                    self.cfg.set(section, key, str(val))

        # Window size
        size = [int(v) for v in self.cfg.get('persistence', 'size').split(',')]
        self.resize(*size)

        # Initial window title
        self.setWindowTitle('Yabsc')
        
        # Actions
        exit = QtGui.QAction('Exit', self)
        exit.setShortcut('Ctrl+Q')
        exit.setStatusTip('Exit yabsc')
        self.connect(exit, QtCore.SIGNAL('triggered()'), QtCore.SLOT('close()'))

        # Status bar
        self.statusBar()
        
        # BuildService object
        self.bs = BuildService()
        if self.cfg.has_option('persistence', 'apiurl'):
            self.bs.apiurl = self.cfg.get('persistence', 'apiurl')

        # Central widgets
        self.maintabwidget = QtGui.QTabWidget()
        self.bsw = BSWidget(self.bs, self.cfg)
        self.maintabwidget.addTab(self.bsw, "Projects")
        self.ww = WorkerWidget(self.bs, self.cfg)
        self.maintabwidget.addTab(self.ww, "Workers")
        self.srw = SubmitRequestWidget.SubmitRequestWidget(self.bs, self.cfg)
        self.maintabwidget.addTab(self.srw, "Submit Requests")
        self.setCentralWidget(self.maintabwidget)
        self.connect(self.maintabwidget, QtCore.SIGNAL('currentChanged(int)'), self.mainTabSelected)
        self.bsw.viewable = True
        self.bsw.enableRefresh()

        # Menu bar
        menubar = self.menuBar()
        file = menubar.addMenu('&File')
        exportaction = QtGui.QAction("&Export ...", self)
        exportaction.setStatusTip("Export current view to file")
        file.addAction(exportaction)
        self.connect(exportaction, QtCore.SIGNAL('triggered()'), self.export)
        file.addAction(exit)
        
        server = menubar.addMenu('&Server')
        self.apiselections = []
        for host in conf.config['auth_dict'].keys():
            apiurl = "%s://%s" % (conf.config['scheme'], host)
            action = QtGui.QAction(apiurl, self)
            action.setStatusTip('Set server to %s' % apiurl)
            server.addAction(action)
            apiselection = ApiSelection(apiurl, self.bsw, self.ww)
            self.apiselections.append(apiselection)
            self.connect(action, QtCore.SIGNAL('triggered()'), apiselection.selected)
        
        settings = menubar.addMenu('S&ettings')
        configureaction = QtGui.QAction("&Configure Yabsc...", self)
        configureaction.setStatusTip("Configure Yabsc options")
        settings.addAction(configureaction)
        self.connect(configureaction, QtCore.SIGNAL('triggered()'), self.configure)

    def export(self):
        """
        export()

        Export current view to file
        """
        tab = self.bsw.tabs[self.bsw.projecttab.currentIndex()]
        model = tab['model']

        dialog = ExportDialog(model)
        ret = dialog.exec_()

        if ret:
            columns = [c['index'] for c in dialog.headers if checkState2bool(c['checkbox'].checkState())]
            separator = dialog.separatormap[str(dialog.sepcombo.currentText())]

            name = ("%s-%s.txt") % (self.bsw.currentproject, tab['name'].lower())

            filename = QtGui.QFileDialog.getSaveFileName(self,
                                                         "Export",
                                                         os.path.join(os.environ['HOME'], name),
                                                         "Text Files (*.txt);;All Files (*.*)")
            if filename:
                try:
                    fout = open(str(filename), 'w')

                    for row in xrange(model.rowCount()):
                        fout.write(separator.join(map(lambda col: model._data(row, col), columns)) + '\n')
                    fout.close()
                except IOError, e:
                    QtGui.QMessageBox.critical(self, "Export Error",
                                                   "Could not write to file %s: %s" % (filename, e))

    def configure(self):
        """
        configure()
        
        Configure Yabsc
        """
        dialog = ConfigureDialog(self)
        dialog.autoscrollcheckbox.setCheckState(bool2checkState(self.cfg.getboolean('general', 'autoscroll')))
        ret = dialog.exec_()
        if ret:
            self.cfg.set('general', 'autoscroll', str(bool(dialog.autoscrollcheckbox.checkState())))
    
    def mainTabSelected(self, tabidx):
        """
        mainTabSelected(tabidx)
        
        Enable refresh for new main tab and disable for others
        """
        for (idx, widget) in enumerate((self.bsw, self.ww, self.srw)):
            if idx == tabidx:
                widget.viewable = True
                widget.enableRefresh()
            else:
                widget.viewable = False
                widget.disableRefresh()
    
    def closeEvent(self, event):
        """
        closeEvent(event)
        
        Event handler for window close
        """
        size = self.frameSize()
        self.cfg.set('persistence', 'size', '%s,%s' % (size.width(), size.height()))
        self.cfg.set('persistence', 'apiurl', self.bs.apiurl)
        self.cfg.set('persistence', 'projectlist', str(self.bsw.projectlistselector.currentIndex()))
        self.cfg.set('persistence', 'project', self.bsw.currentproject)
        try:
            f = open(self.cfgfilename, 'w')
            self.cfg.write(f)
            f.close()
        except IOError, e:
            QtGui.QMessageBox.critical(self, "Configuration File Error",
                                       "Could not write configuration file %s: %s" % (self.cfgfilename, e))
        QtGui.QMainWindow.closeEvent(self, event)
