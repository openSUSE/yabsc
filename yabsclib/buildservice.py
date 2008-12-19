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

def flag2bool(flag):
    """
    flag2bool(flag) -> Boolean
    
    Returns a boolean corresponding to the string 'enable', or 'disable'
    """
    if flag == 'enable':
        return True
    elif flag == 'disable':
        return False

def bool2flag(b):
    """
    bool2flag(b) -> String
    
    Returns 'enable', or 'disable' according to boolean value b
    """
    if b == True:
        return 'enable'
    elif b == False:
        return 'disable'


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
        if not watchlist:
            watchlist = ElementTree.SubElement(person, 'watchlist')
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
        core.get_binary_file(self.apiurl, project, repo, arch, file, target_filename=path, package=package)
        
    def getBuildLog(self, project, target, package, offset=0):
        """
        getBuildLog(project, target, package, offset=0) -> str
        
        Returns the build log of a package for a particular target.
        
        If offset is greater than 0, return only text after that offset. This allows live streaming
        """
        (repo, arch) = target.split('/')
        u = core.makeurl(self.apiurl, ['build', project, repo, arch, package, '_log?nostream=1&start=%s' % offset])
        return core.http_GET(u).read()
    
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

            d = {'id': int(sr.get('id'))}
            sb = sr.findall('submit')[0]
            src = sb.findall('source')[0]
            d['srcproject'] = src.get('project')
            d['srcpackage'] = src.get('package')
            dst = sb.findall('target')[0]
            d['dstproject'] = dst.get('project')
            d['dstpackage'] = dst.get('package')
            d['state'] = sr.findall('state')[0].get('name')

            submitrequests.append(d)
        submitrequests.sort(key='id')
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
    
    def abortBuild(self, project, package=None, target=None):
        """
        abort(project, package=None, target=None)

        Abort build of a package or all packages in a project
        """
        if target:
            (repo, arch) = target.split('/')
        else:
            repo = None
            arch = None
        return core.abortbuild(self.apiurl, project, package, arch, repo)

    def getBuildHistory(self, project, package, target):
        """
        getBuildHistory(project, package, target) -> list
        
        Get build history of package for target as a list of tuples of the form
        (time, srcmd5, rev, versrel, bcnt)
        """
        (repo, arch) = target.split('/')
        u = core.makeurl(self.apiurl, ['build', project, repo, arch, package, '_history'])
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        r = []
        for node in root.findall('entry'):
            rev = int(node.get('rev'))
            srcmd5 = node.get('srcmd5')
            versrel = node.get('versrel')
            bcnt = int(node.get('bcnt'))
            t = time.localtime(int(node.get('time')))
            t = time.strftime('%Y-%m-%d %H:%M:%S', t)

            r.append((t, srcmd5, rev, versrel, bcnt))
        return r

    def getCommitLog(self, project, package, revision=None):
        """
        getCommitLog(project, package, revision=None) -> list
        
        Get commit log for package in project. If revision is set, get just the
        log for that revision.
        
        Each log is a tuple of the form (rev, srcmd5, version, time, user,
        comment)
        """
        u = core.makeurl(self.apiurl, ['source', project, package, '_history'])
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        r = []
        revisions = root.findall('revision')
        revisions.reverse()
        for node in revisions:
            rev = int(node.get('rev'))
            if revision and rev != int(revision):
                continue
            srcmd5 = node.find('srcmd5').text
            version = node.find('version').text
            user = node.find('user').text
            try:
                comment = node.find('comment').text
            except:
                comment = '<no message>'
            t = time.localtime(int(node.find('time').text))
            t = time.strftime('%Y-%m-%d %H:%M:%S', t)

            r.append((rev, srcmd5, version, t, user, comment))
        return r
    
    def getProjectMeta(self, project):
        """
        getProjectMeta(project) -> string
        
        Get XML metadata for project
        """
        return ''.join(core.show_project_meta(self.apiurl, project))
    
    def getPackageMeta(self, project, package):
        """
        getPackageMeta(project, package) -> string
        
        Get XML metadata for package in project
        """
        return ''.join(core.show_package_meta(self.apiurl, project, package))
    
    def projectFlags(self, project):
        """
        projectFlags(project) -> ProjectFlags
        
        Return a ProjectFlags object for manipulating the flags of project
        """
        return ProjectFlags(self, project)


class ProjectFlags(object):
    """
    ProjectFlags(bs, project)
    
    Represents the flags in project through the BuildService object bs
    """
    def __init__(self, bs, project):
        self.bs = bs
        self.tree = ElementTree.fromstring(self.bs.getProjectMeta(project))

        # The "default" flags, when undefined
        self.defaultflags = {'build': True,
                             'publish': True,
                             'useforbuild': True,
                             'debuginfo': False}

        # Figure out what arches and repositories are defined
        self.arches = {}
        self.repositories = {}
        
        # Build individual repository list
        for repository in self.tree.findall('repository'):
            repodict = {'arches': {}}
            self.__init_flags_in_dict(repodict)
            for arch in repository.findall('arch'):
                repodict['arches'][arch.text] = {}
                self.__init_flags_in_dict(repodict['arches'][arch.text])
                # Add placeholder in global arches
                self.arches[arch.text] = {}
            self.repositories[repository.get('name')] = repodict
        
        # Initialise flags in global arches
        for archdict in self.arches.values():
            self.__init_flags_in_dict(archdict)
        
        # A special repository representing the global and global arch flags
        self.allrepositories = {'arches': self.arches}
        self.__init_flags_in_dict(self.allrepositories)
        
        # Now populate the structures from the xml data
        for flagtype in ('build', 'publish', 'useforbuild', 'debuginfo'):
            flagnode = self.tree.find(flagtype)
            if flagnode:
                for node in flagnode:
                    repository = node.get('repository')
                    arch = node.get('arch')
                    
                    if repository and arch:
                        self.repositories[repository]['arches'][arch][flagtype] = flag2bool(node.tag)
                    elif repository:
                        self.repositories[repository][flagtype] = flag2bool(node.tag)
                    elif arch:
                        self.arches[flagtype] = flag2bool(node.tag)
                    else:
                        self.allrepositories[flagtype] = flag2bool(node.tag)

    def __init_flags_in_dict(self, d):
        """
        __init_flags_in_dict(d)
        
        Initialize all build flags to None in d
        """
        d.update({'build': None,
                  'publish': None,
                  'useforbuild': None,
                  'debuginfo': None})
    
    def save(self):
        """
        save()
        
        Save flags
        """
        
        for flagtype in ('build', 'publish', 'useforbuild', 'debuginfo'):
            # Clear if set
            flagnode = self.tree.find(flagtype)
            if flagnode:
                self.tree.remove(flagnode)
            
            # Generate rule nodes
            rulenodes = []
            
            # globals
            if self.allrepositories[flagtype] != None:
                rulenodes.append(ElementTree.Element(bool2flag(self.allrepositories[flagtype])))
            for arch in self.arches:
                if self.arches[arch][flagtype] != None:
                    rulenodes.append(ElementTree.Element(bool2flag(self.arches[arch][flagtype]), arch=arch))
            
            # repositories
            for repository in self.repositories:
                if self.repositories[repository][flagtype] != None:
                    rulenodes.append(ElementTree.Element(bool2flag(self.repositories[repository][flagtype]), repository=repository))
                for arch in self.repositories[repository]['arches']:
                    if self.repositories[repository]['arches'][arch][flagtype] != None:
                        rulenodes.append(ElementTree.Element(bool2flag(self.repositories[repository]['arches'][arch][flagtype]), arch=arch, repository=repository))
        
            # Add nodes to tree
            if rulenodes:
                from pprint import pprint
                pprint(rulenodes)
                flagnode = ElementTree.Element(flagtype)
                self.tree.insert(3, flagnode)
                for rulenode in rulenodes:
                    flagnode.append(rulenode)

        print ElementTree.tostring(self.tree)
    
