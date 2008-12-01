#
# results.py - Result widget for Yabsc
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

import os
from PyQt4 import QtGui, QtCore

#
# Data model
#

class ResultModel(QtCore.QAbstractItemModel):
    """ResultModel()
    
    Model for package results
    """
    def __init__(self):
        QtCore.QAbstractItemModel.__init__(self)
        self.results = []
        self.targets = []
        self.targetfilter = ""
        self.resultfilter = ""
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
        self.updateVisiblePackages(reset=False)
        self.updateVisibleTargets(reset=False)
        self.reset()
    
    def _targetIndexFromName(self, target):
        """
        _targetIndexFromName(target)
        
        Returns the column index of the named target in the raw result data
        """
        return self.targets.index(target)
    
    def targetFromColumn(self, column):
        """
        targetFromColumn(column)
        
        Returns the target represented by the visible 'column'
        """
        if column > 0:
            return self.targets[self._targetIndexFromName(self.visibletargets[column-1])]
    
    def getPackageTargetsWithStatus(self, package, status):
        """
        getPackageTargetsWithStatus(package, status) -> list
        
        Returns a list of failed targets for a package
        """
        targets = []
        for (i, target) in enumerate(self.results[package]):
            if target == status.lower():
                targets.append(self.targets[i])
        return targets

    def _data(self, row, column):
        """
        _data(row, column) -> str
        
        Internal method for getting model data. The 0th column is the package name, and subsequent
        columns are result codes
        """
        package = self.visiblepackages[row]
        target = self.visibletargets[column-1]
        if column == 0:
            return package
        else:
            return self.results[package][self._targetIndexFromName(target)]
    
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
    
    def packageHasResult(self, package, result):
        """
        packageHasResult(package, result) -> boolean
        
        Return whether a package has a result in one of the visible targets
        """
        for (i, target) in enumerate(self.targets):
            if target in self.visibletargets and self.results[package][i] == result:
                return True
        return False
    
    def numPackagesWithResult(self, result):
        """
        numPackagesWithResult(result)
        
        Return the number of packages with result in one of the visible targets
        """
        packages = [p for p in self.packages if self.packagefilter in p]
        result = result.lower()
        if result == 'all':
            return len(packages)
        return len([p for p in packages if self.packageHasResult(p, result)])

    def updateVisiblePackages(self, reset=True):
        """
        updateVisiblePackages(reset=True)
        
        Update the list of visible packages
        """
        # Start with all packages
        self.visiblepackages = self.packages

        # Apply filter string
        if self.packagefilter:
            self.visiblepackages = [p for p in self.visiblepackages if self.packagefilter in p]
        
        # Apply result filter
        if self.resultfilter:
            self.visiblepackages = [p for p in self.visiblepackages if self.packageHasResult(p, self.resultfilter)]
        
        if reset:
            self.reset()
    
    def setPackageFilter(self, filterstring, reset=True):
        """
        setPackageFilter(filterstring)
        
        Only show packages matching filterstring
        """
        self.packagefilter = filterstring
        self.updateVisiblePackages(reset)

    def setResultFilter(self, result="", reset=True):
        """
        setResultFilter(target)
        
        Only show packages with at least one result matching 'result'. If
        'result' is undefined or empty, filter is disabled
        """
        self.resultfilter = result.lower()
        self.updateVisiblePackages(reset)

    def updateVisibleTargets(self, reset=True):
        """
        updateVisibleTargets(reset=True)
        
        Update the list of visible targets
        """
        self.visibletargets = self.targets
        
        if self.targetfilter:
            self.visibletargets = [t for t in self.targets if t == self.targetfilter]
        
        if reset:
            self.reset()
        
    def setTargetFilter(self, target="", reset=True):
        """
        setTargetFilter(target)
        
        Only show results for target. If target is undefined or empty, filter
        is disabled
        """
        self.targetfilter = target
        self.updateVisibleTargets(reset)

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


class ProjectTreeView(QtGui.QTreeView):
    """
    ProjectTreeView(bs, parent=None)
    
    The project tree view. 'bs' must be a BuildService object
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
        project = self.model().data(index, QtCore.Qt.DisplayRole).toString()
        if project:
            menu = QtGui.QMenu()
            
            watchaction = None
            unwatchaction = None
            
            abortaction = QtGui.QAction('Abort all builds for %s' % project, self)
            menu.addAction(abortaction)
            
            # Disable until feature is finished
            # editflagsaction = QtGui.QAction('Edit flags for %s' % project, self)
            # menu.addAction(editflagsaction)
            
            if project in self.bs.getWatchedProjectList():
                unwatchaction = QtGui.QAction('Unwatch %s' % project, self)
                menu.addAction(unwatchaction)
            else:
                watchaction = QtGui.QAction('Watch %s' % project, self)
                menu.addAction(watchaction)
            
            selectedaction = menu.exec_(self.mapToGlobal(event.pos()))
            
            if selectedaction:
                try:
                    if selectedaction == abortaction:
                        self.bs.abortBuild(str(project))
                    elif selectedaction == editflagsaction:
                        self.editFlags(project)
                    elif selectedaction == watchaction:
                        self.bs.watchProject(project)
                    elif selectedaction == unwatchaction:
                        self.bs.unwatchProject(project)
                except Exception, e:
                    QtGui.QMessageBox.critical(self, "Error",
                               "Could not perform action on project %s: %s" % (project, e))
                    raise
                if selectedaction in (watchaction, unwatchaction):
                    self.emit(QtCore.SIGNAL("watchedProjectsChanged()"))

    def editFlags(self, project):
        """
        editFlags(project)
        
        Edit flags for project
        """
        flags = self.bs.projectFlags(project)
        dialog = ProjectFlagsDialog(project, flags)
        ret = dialog.exec_()
        if ret:
            flags.save()

class ResultTreeView(QtGui.QTreeView):
    """
    ResultTreeView(bs, parent=None)
    
    The result tree view. 'parent' must contain a BuildService object, 'bs' and
    the current project, 'currentproject'
    """
    def __init__(self, parent=None):
        self.parent = parent
        QtGui.QTreeView.__init__(self, parent)
    
    def contextMenuEvent(self, event):
        """
        contextMenuEvent(event)
        
        Context menu event handler
        """
        index = self.indexAt(event.pos())
        packageindex = self.model().createIndex(index.row(), 0)
        packagename = str(self.model().data(packageindex, QtCore.Qt.DisplayRole).toString())
        target = self.model().targetFromColumn(index.column())
        failedtargets = self.model().getPackageTargetsWithStatus(packagename, 'failed')
        buildingtargets = self.model().getPackageTargetsWithStatus(packagename, 'building')
        scheduledtargets = self.model().getPackageTargetsWithStatus(packagename, 'scheduled')
        
        if packagename:
            menu = QtGui.QMenu()
            
            rebuildtargetaction = None
            rebuildallfailedaction = None
            aborttargetaction = None
            abortallaction = None
            
            if target:
                rebuildtargetaction = QtGui.QAction('Rebuild %s for %s' % (packagename, target), self)
                menu.addAction(rebuildtargetaction)
                
            if failedtargets:
                rebuildallfailedaction = QtGui.QAction('Rebuild %s for all failed targets' % packagename, self)
                menu.addAction(rebuildallfailedaction)

            rebuildallaction = QtGui.QAction('Rebuild %s for all targets' % packagename, self)
            menu.addAction(rebuildallaction)

            if target and (target in buildingtargets or target in scheduledtargets):
                aborttargetaction = QtGui.QAction('Abort build of %s for %s' % (packagename, target), self)
                menu.addAction(aborttargetaction)
            
            if buildingtargets or scheduledtargets:
                abortallaction = QtGui.QAction('Abort all builds of %s' % packagename, self)
                menu.addAction(abortallaction)

            selectedaction = menu.exec_(self.mapToGlobal(event.pos()))
            
            if selectedaction:
                try:
                    if selectedaction == rebuildtargetaction:
                        self.parent.bs.rebuild(self.parent.currentproject, packagename, target=target)
                    elif selectedaction == rebuildallfailedaction:
                        self.parent.bs.rebuild(self.parent.currentproject, packagename, code='failed')
                    elif selectedaction == rebuildallaction:
                        self.parent.bs.rebuild(self.parent.currentproject, packagename)
                    elif selectedaction == aborttargetaction:
                        self.parent.bs.abortBuild(self.parent.currentproject, packagename, target)                        
                    elif selectedaction == abortallaction:
                        self.parent.bs.abortBuild(self.parent.currentproject, packagename)
                except Exception, e:
                    QtGui.QMessageBox.critical(self, "Error",
                               "Could not perform action on package %s: %s" % (packagename, e))
                    raise


class ProjectFlagsDialog(QtGui.QDialog):
    """
    ProjectFlagsDialog()
    
    Project flags configuration dialog
    """
    def __init__(self, project, flags, parent=None):
        QtGui.QDialog.__init__(self, parent)
        
        self.setWindowTitle("Project Flags for %s" % project)
        
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


#
# Result widget
#
class ResultWidget(QtGui.QWidget):
    """
    ResultWidget(bs, cfg)
    
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
        self.projecttreeview = ProjectTreeView(self.bs)
        self.projecttreeview.setRootIsDecorated(False)
        self.projectlistmodel = QtGui.QStandardItemModel(0, 1, self)
        self.projectlistmodel.setHeaderData(0, QtCore.Qt.Horizontal, QtCore.QVariant("Project"))
        self.projectlistthread = ProjectListThread(self.bs)
        self.refreshProjectList()
        self.projecttreeview.setModel(self.projectlistmodel)
        QtCore.QObject.connect(self.projecttreeview, QtCore.SIGNAL("clicked(const QModelIndex&)"), self.projectSelected)
        QtCore.QObject.connect(self.projecttreeview, QtCore.SIGNAL("watchedProjectsChanged()"), self.refreshProjectList)
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
        
        self.resulttab = QtGui.QTabBar()
        QtCore.QObject.connect(self.resulttab, QtCore.SIGNAL("currentChanged(int)"), self.filterResult)
        self.tabs = []
        
        for tabname in ('All', 'Succeeded', 'Failed', 'Building', 'Blocked', 'Scheduled', 'Expansion Error', 'Broken', 'Disabled'):
            self.resulttab.addTab(tabname)
            self.tabs.append(tabname)

        # Project results
        self.resultview = ResultTreeView(self)
        self.resultview.setRootIsDecorated(False)
        self.resultmodel = ResultModel()
        self.resultview.setModel(self.resultmodel)
        QtCore.QObject.connect(self.resultview, QtCore.SIGNAL("clicked(const QModelIndex&)"), self.refreshPackageInfo)


        # Result refresh
        self.refreshtimer = QtCore.QTimer()
        QtCore.QObject.connect(self.refreshtimer, QtCore.SIGNAL("timeout()"), self.timerRefresh)
        self.projectresultsthread = ProjectResultsThread(self.bs)
        QtCore.QObject.connect(self.projectresultsthread, QtCore.SIGNAL("finished()"), self.updatePackageList)

        # Package info
        self.packageinfo = QtGui.QTextBrowser()
        self.packageinfo.setReadOnly(True)
        self.packageinfo.setOpenLinks(False)
        QtCore.QObject.connect(self.packageinfo, QtCore.SIGNAL("anchorClicked(const QUrl&)"), self.infoClick)
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
        packagelistlayout.addWidget(self.resulttab)
        packagelistlayout.addWidget(self.resultview)
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

    def updatePackageList(self):
        """
        updatePackageList()
        
        Update package list data from result in self.projectresultsthread
        """
        results = self.projectresultsthread.results
        targets = self.projectresultsthread.targets
        self.resultmodel.setResults(results, targets)
        self.resizeColumns()
        self.updateResultCounts()
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
        tabname = self.tabs[self.resulttab.currentIndex()]
        column = modelindex.column()
        row = modelindex.row()
        package = self.resultmodel.packageFromRow(row)
        if column > 0:
            statuscode = self.resultmodel._data(row, column)
            if statuscode in ("succeeded", "building", "failed"):
                target = self.resultmodel.visibletargets[column-1]
                self.viewBuildOutput(target, package)
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
        pitext += "<table width='90%'>"
        status = self.packagestatusthread.status
        for target in sorted(status.keys()):
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
                pitext += "<a href='buildlog,%s,%s'>%s</a>" % (target, package, statustext)
            else:
                pitext += statustext
            pitext += "</b></font></td>"
            pitext += "<td><a href='buildhistory,%s,%s'><b>buildhistory</b></a></td>" % (target, package)
            pitext += "<td><a href='binaries,%s,%s'><b>binaries</b></a></td></tr>" % (target, package)
        pitext += "</table>"
        
        pitext += "<p><a href='commitlog,%s'><b>commitlog</b></a></p>" % package
        
        self.packageinfo.setWordWrapMode(QtGui.QTextOption.WordWrap)
        self.packageinfo.setText(pitext)

    def infoClick(self, url):
        """
        infoClick(url)
        
        Handle url clicks in the package info view
        """
        args = str(url.toString()).split(',')
        if args[0] == 'buildlog':
            self.viewBuildOutput(*args[1:])
        elif args[0] == 'binaries':
            self.viewBinaries(*args[1:])
        elif args[0] == 'getbinary':
            self.getBinary(*args[1:])
        elif args[0] == 'buildhistory':
            self.viewBuildHistory(*args[1:])
        elif args[0] == 'commitlog':
            self.viewCommitLog(*args[1:])

    def viewBinaries(self, target, package):
        """
        viewBinaries(target, package)
        
        View binaries for target and package
        """
        pitext = "<h2>%s binaries for %s</h2>" % (package, target)
        binaries = self.bs.getBinaryList(self.currentproject, target, package)
        if binaries:
            pitext += "<table>"
            for binary in sorted(binaries):
                pitext += "<tr><td><a href='getbinary,%s,%s,%s'>%s</a></td></tr>" % (target, package, binary, binary)
            pitext += "</table>"
        else:
            pitext += "<b>No binaries</b>"

        self.packageinfo.setWordWrapMode(QtGui.QTextOption.WordWrap)
        self.packageinfo.setText(pitext)
    
    def getBinary(self, target, package, file):
        """
        getBinary(target, file)
        
        Save 'file' in 'target' to a local path
        """
        path = QtGui.QFileDialog.getSaveFileName(self,
                                                 "Save binary",
                                                 os.path.join(os.environ['HOME'], file),
                                                 "RPM Files (*.rpm);;All Files (*.*)")
        if path:
            try:
                self.bs.getBinary(self.currentproject, target, package, file, path)
            except Exception, e:
                QtGui.QMessageBox.critical(self, "Binary Save Error",
                                                 "Could not save binary to %s: %s" % (path, e))
                raise

    def viewBuildHistory(self, target, package):
        """
        viewBuildHistory(target, package)
        
        View build history of package for target
        """
        pitext = "<h2>Build History of %s for %s</h2>" % (package, target)
        history = self.bs.getBuildHistory(self.currentproject, package, target)
        
        if history:
            pitext += "<table width='90%'><tr><td><b>Time</b></td><td><b>Source MD5</b></td><td><b>Revision</b></td><td><b>Version-Release.Buildcount</b></td></tr>"
            
            for entry in history:
                pitext += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s.%s</td></tr>" % entry
            pitext += "</table>"
        else:
            pitext += "<b>No history</b>"

        self.packageinfo.setWordWrapMode(QtGui.QTextOption.WordWrap)
        self.packageinfo.setText(pitext)

    def viewCommitLog(self, package):
        """
        viewCommitLog(package)
        
        View commit log of package
        """
        pitext = "<h2>Commit Log of %s</h2>" % package
        commitlog = self.bs.getCommitLog(self.currentproject, package)
        
        if commitlog:            
            for entry in commitlog:
                pitext += "<hr/><p>Revision <b>%s</b> - MD5 <b>%s</b> - Version <b>%s</b><br/>Modified <em>%s</em> by <em>%s</em><pre>%s</pre></p>" % entry
        else:
            pitext += "<b>No log</b>"

        self.packageinfo.setWordWrapMode(QtGui.QTextOption.WordWrap)
        self.packageinfo.setText(pitext)

    def viewBuildOutput(self, target, package):
        """
        viewBuildOutput(target, package)
        
        Show build output for target and package. If the package is currently
        building, stream the output until it is finished
        """
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
        self.resultmodel.setPackageFilter(str(filterstring))
        self.resizeColumns()
        self.updateResultCounts()
        
    def filterTarget(self, target):
        if target != 'All':
            self.resultmodel.setTargetFilter(str(target))
        else:
            self.resultmodel.setTargetFilter()
        self.resizeColumns()
        self.updateResultCounts()

    def filterResult(self, resultindex):
        if self.tabs:
            result = self.tabs[resultindex]
            if result != 'All':
                self.resultmodel.setResultFilter(result)
            else:
                self.resultmodel.setResultFilter()
            self.resizeColumns()
            self.updateResultCounts()

    def resizeColumns(self):
        """
        resizeColumns()
        
        Resize columns to fit contents
        """
        for column in range(self.resultmodel.columnCount()):
            self.resultview.resizeColumnToContents(column)

    def updateResultCounts(self):
        """
        updateResultCounts()
        
        Update package counts for result tabs
        """
        for tab in self.tabs:
            self.resulttab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab, self.resultmodel.numPackagesWithResult(tab)))
