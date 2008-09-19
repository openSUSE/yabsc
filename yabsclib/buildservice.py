#
# buildservice.py - Buildservice API support for Yabsc
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
import tempfile
import time
import urlparse
import xml.etree.cElementTree as ElementTree
from PyQt4 import QtCore
from osc import conf, core

class metafile:
    """
    metafile(url, input, change_is_required=False, file_ext='.xml')
    
    Implementation on osc.core.metafile that does not print to stdout
    """
    def __init__(self, url, input, change_is_required=False, file_ext='.xml'):
        self.url = url
        self.change_is_required = change_is_required

        (fd, self.filename) = tempfile.mkstemp(prefix = 'osc_metafile.', suffix = file_ext, dir = '/tmp')

        f = os.fdopen(fd, 'w')
        f.write(''.join(input))
        f.close()

        self.hash_orig = core.dgst(self.filename)

    def sync(self):
        hash = core.dgst(self.filename)
        if self.change_is_required == True and hash == self.hash_orig:
            os.unlink(self.filename)
            return True

        # don't do any exception handling... it's up to the caller what to do in case
        # of an exception
        core.http_PUT(self.url, file=self.filename)
        os.unlink(self.filename)
        return True

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
        for host in conf.config['api_host_options'].keys():
            apiurl = "%s://%s" % (conf.config['scheme'], host)
        return apiservers
    
    def getUserName(self):
        """getUserName() -> str
        
        Get the user name associated with the current API server
        """
        hostname = urlparse.urlparse(self.apiurl)[1]
        return conf.config['api_host_options'][hostname]['user']
    
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
    
    def watchProject(self, project):
        """
        watchProject(project)
        
        Watch project
        """
        username = self.getUserName()
        data = core.meta_exists('user', username, create_new=False, apiurl=self.apiurl)
        url = core.make_meta_url('user', username, self.apiurl)

        person = ElementTree.fromstring(''.join(data))
        watchlist = person.find('watchlist')
        ElementTree.SubElement(watchlist, 'project', name=str(project))
        
        f = metafile(url, ElementTree.tostring(person))
        f.sync()

    def unwatchProject(self, project):
        """
        watchProject(project)
        
        Watch project
        """
        username = self.getUserName()
        data = core.meta_exists('user', username, create_new=False, apiurl=self.apiurl)
        url = core.make_meta_url('user', username, self.apiurl)

        person = ElementTree.fromstring(''.join(data))
        watchlist = person.find('watchlist')
        for node in watchlist:
            if node.get('name') == str(project):
                watchlist.remove(node)
                break
        
        f = metafile(url, ElementTree.tostring(person))        
        f.sync()

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
        return core.get_binarylist(self.apiurl, project, repo, arch, package)
    
    def getBinary(self, project, target, package, file, path):
        """
        getBinary(project, target, file, path)
        
        Get binary 'file' for 'project' and 'target' and save it as 'path'
        """
        (repo, arch) = target.split('/')
        core.get_binary_file(self.apiurl, project, repo, arch, file, targetfilename=path, package=package)
        
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
    
    def getWaitStats(self):
        """
        getWaitStats() -> list
        
        Returns the number of jobs in the wait queue as a list of (arch, count)
        pairs
        """
        url = core.makeurl(self.apiurl, ['build', '_workerstatus'])
        f = core.http_GET(url)
        tree = ElementTree.parse(f).getroot()
        stats = []
        for worker in tree.findall('waiting'):
            stats.append((worker.get('arch'), int(worker.get('jobs'))))
        return stats

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
    
    def rebuild(self, project, package, target=None, code=None):
        """
        rebuild(project, package, target, code=None)

        Rebuild 'package' in 'project' for 'target'. If 'code' is specified,
        all targets with that code will be rebuilt
        """
        if target:
            (repo, arch) = target.split('/')
        else:
            repo = None
            arch = None
        return core.rebuild(self.apiurl, project, package, repo, arch, code)
