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
        return len([p for p in self.visiblepackages if self.packageHasResult(p, result)])

    def updateVisiblePackages(self, reset=True):
        """
        updateVisiblePackages(reset=True)
        
        Update the list of visible packages
        """
        # Start with all packages
        self.visiblepackages = self.packages

        # Apply filter string
        if self.packagefilter:
            self.visiblepackages = [p for p in self.visiblepackages if filterstring in p]
        
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
        
        self.resulttab = QtGui.QTabBar()
        QtCore.QObject.connect(self.resulttab, QtCore.SIGNAL("currentChanged(int)"), self.filterResult)
        self.tabs = []
        
        for tabname in ('All', 'Succeeded', 'Failed', 'Building', 'Blocked', 'Scheduled', 'Expansion Error', 'Broken', 'Disabled'):
            self.resulttab.addTab(tabname)
            self.tabs.append(tabname)

        # Project results
        self.resultview = QtGui.QTreeView()
        self.resultview.setRootIsDecorated(False)
        self.resultmodel = ResultModel()
        self.resultview.setModel(self.resultmodel)
        QtCore.QObject.connect(self.resultview, QtCore.SIGNAL("clicked(const QModelIndex&)"), self.refreshPackageInfo)


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

    def updatePackageLists(self):
        """
        updatePackageLists()
        
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
        for column in range(self.resultmodel.columnCount()):
            self.resultview.resizeColumnToContents(column)

    def updateResultCounts(self):
        """
        updateResultCounts()
        
        Update package counts for result tabs
        """
        for tab in self.tabs:
            self.resulttab.setTabText(self.tabs.index(tab), "%s (%d)" % (tab, self.resultmodel.numPackagesWithResult(tab)))



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
