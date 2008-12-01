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

import ConfigParser
import os
from PyQt4 import QtGui, QtCore
from osc import conf

import util
import buildservice
import results
import workers
import submitrequests

defaultconfig = {'general': {'autoscroll': False},
                 'persistence': {'size': '900,725'}}

class ApiSelection:
    """
    ApiSelection(apiurl, *args)
    
    Allows the selection of an apiurl to propagate to multiple display widgets
    that have implemented the setApiurl method
    """
    def __init__(self, apiurl, *args):
       self.apiurl = apiurl
       self.widgets = args
       
    def selected(self):
        """
        selected(self)
        
        Set apiurl of the widgets to that represented by this object
        """
        for widget in self.widgets:
            widget.setApiurl(self.apiurl)

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
            checkbox.setCheckState(util.bool2checkState(True))
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


class WaitStatsThread(QtCore.QThread):
    """
    WaitStatsThread(bs)
    
    Thread for retrieving wait stats. Requires a BuildService object
    """
    def __init__(self, bs):
        QtCore.QThread.__init__(self)
        self.bs = bs
        self.stats = []
    
    def run(self):
        self.stats = self.bs.getWaitStats()


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
        self.statslabel = QtGui.QLabel()
        self.statusBar().addPermanentWidget(self.statslabel)
        
        # BuildService object
        self.bs = buildservice.BuildService()
        if self.cfg.has_option('persistence', 'apiurl'):
            self.bs.apiurl = self.cfg.get('persistence', 'apiurl')
        
        # Wait stats
        self.waitstatstimer = QtCore.QTimer()
        QtCore.QObject.connect(self.waitstatstimer, QtCore.SIGNAL("timeout()"), self.refreshWaitStats)
        self.waitstatsthread = WaitStatsThread(self.bs)
        QtCore.QObject.connect(self.waitstatsthread, QtCore.SIGNAL("finished()"), self.updateWaitStats)
        self.waitstatstimer.start(10000)

        # Central widgets
        self.maintabwidget = QtGui.QTabWidget()
        self.rw = results.ResultWidget(self.bs, self.cfg)
        self.maintabwidget.addTab(self.rw, "Projects")
        self.ww = workers.WorkerWidget(self.bs, self.cfg)
        self.maintabwidget.addTab(self.ww, "Workers")
        self.srw = submitrequests.SubmitRequestWidget(self.bs, self.cfg)
        self.maintabwidget.addTab(self.srw, "Submit Requests")
        self.setCentralWidget(self.maintabwidget)
        self.connect(self.maintabwidget, QtCore.SIGNAL('currentChanged(int)'), self.mainTabSelected)
        self.rw.viewable = True
        self.rw.enableRefresh()

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
        for apiurl in conf.config['api_host_options'].keys():
            if not apiurl.startswith('http'):
                apiurl = "%s://%s" % (conf.config['scheme'], apiurl)
            action = QtGui.QAction(apiurl, self)
            action.setStatusTip('Set server to %s' % apiurl)
            server.addAction(action)
            apiselection = ApiSelection(apiurl, self.rw, self.ww)
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
        tab = self.rw.tabs[self.rw.resulttab.currentIndex()]

        dialog = ExportDialog(self.rw.resultmodel)
        ret = dialog.exec_()

        if ret:
            columns = [c['index'] for c in dialog.headers if util.checkState2bool(c['checkbox'].checkState())]
            separator = dialog.separatormap[str(dialog.sepcombo.currentText())]

            name = ("%s-%s.txt") % (self.rw.currentproject, tab.lower())

            filename = QtGui.QFileDialog.getSaveFileName(self,
                                                         "Export",
                                                         os.path.join(os.environ['HOME'], name),
                                                         "Text Files (*.txt);;All Files (*.*)")
            if filename:
                try:
                    fout = open(str(filename), 'w')

                    for row in xrange(self.rw.resultmodel.rowCount()):
                        fout.write(separator.join(map(lambda col: self.rw.resultmodel._data(row, col), columns)) + '\n')
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
        dialog.autoscrollcheckbox.setCheckState(util.bool2checkState(self.cfg.getboolean('general', 'autoscroll')))
        ret = dialog.exec_()
        if ret:
            self.cfg.set('general', 'autoscroll', str(bool(dialog.autoscrollcheckbox.checkState())))
    
    def mainTabSelected(self, tabidx):
        """
        mainTabSelected(tabidx)
        
        Enable refresh for new main tab and disable for others
        """
        for (idx, widget) in enumerate((self.rw, self.ww, self.srw)):
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
        self.cfg.set('persistence', 'projectlist', str(self.rw.projectlistselector.currentIndex()))
        self.cfg.set('persistence', 'project', self.rw.currentproject)
        try:
            f = open(self.cfgfilename, 'w')
            self.cfg.write(f)
            f.close()
        except IOError, e:
            QtGui.QMessageBox.critical(self, "Configuration File Error",
                                       "Could not write configuration file %s: %s" % (self.cfgfilename, e))
        QtGui.QMainWindow.closeEvent(self, event)

    def refreshWaitStats(self):
        """
        refreshWaitStats()
        
        Refresh wait stats
        """
        self.waitstatstimer.stop()
        self.waitstatsthread.start()
    
    def updateWaitStats(self):
        """
        updateWaitStats()
        
        Update wait stats in the status bar from the last result
        """
        s = "Waiting"
        for (arch, count) in self.waitstatsthread.stats:
            s += "  | <b>%s</b> - <b>%s</b>" % (arch, count)
        self.statslabel.setText(s)
        self.waitstatstimer.start()
