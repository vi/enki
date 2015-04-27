"""
session --- Reopen files when starting
======================================
"""

import sys
import os.path
import json

from enki.core.core import core
from enki.core.defines import CONFIG_DIR
import enki.core.json_wrapper


def getSessionFilePath():
    if core.commandLineArgs()['session_name']:
        session_name = core.commandLineArgs()['session_name']
    elif 'ENKI_SESSION' in os.environ:
        session_name = os.environ['ENKI_SESSION']
    else:
        session_name = ''

    if session_name:
        session_filename = 'session_{}.json'.format(session_name)

        for char in r'<>:"/\|?*' + ' ':  # reserved characters for file name on Windows. By MSDN. And space
            session_filename = session_filename.replace(char, '_')
    else:
        session_filename = 'session.json'

    return os.path.join(CONFIG_DIR, session_filename)

def getSocketFilePath():
    return getSessionFilePath().replace(".json",".socket")

def openSessionSocket(sfp):
    import socket
    try:
        os.unlink(sfp)
    except OSError:
        if os.path.exists(sfp):
            raise
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(sfp);
    sock.listen(2);
    return sock;

def sessionSocketListener():
    from PyQt4.QtCore import QObject, pyqtSignal
    import socket
    class Foo(QObject):
        qqq = pyqtSignal(['QString'])
    f = Foo()
    f.qqq.connect(core.workspace().openFile);
    
    sock = openSessionSocket (getSocketFilePath())

    while True:
        connection, client_address = sock.accept()
        try:
            data = connection.recv(4096)
            if data:
                if (data.startswith("open ")):
                    f.qqq.emit(data[5:])
        finally:
            # Clean up the connection
            connection.close()


def startSessionSocketListener():
    import thread;
    thread.start_new_thread(sessionSocketListener, ())


_SESSION_FILE_PATH = getSessionFilePath()

class Plugin:
    """Plugin interface
    """
    def __init__(self):
        core.restoreSession.connect(self._onRestoreSession)
        core.aboutToTerminate.connect(self._onAboutToTerminate)

        startSessionSocketListener()


    def del_(self):
        """Explicitly called destructor
        """
        pass

    def _onRestoreSession(self):
        """Enki initialisation finished.
        Now restore session
        """
        # if have documents except 'untitled' new doc, don't restore session
        if core.workspace().currentDocument() is not None:
            return

        if not os.path.exists(_SESSION_FILE_PATH):
            return

        session = enki.core.json_wrapper.load(_SESSION_FILE_PATH, 'session', None)

        if session is not None:
            for filePath in session['opened']:
                if os.path.exists(filePath):
                    core.workspace().openFile(filePath)

            if session['current'] is not None:
                document = self._documentForPath(session['current'])
                if document is not None: # document might be already deleted
                    core.workspace().setCurrentDocument(document)

    def _documentForPath(self, filePath):
        """Find document by it's file path.
        Raises ValueError, if document hasn't been found
        """
        for document in core.workspace().documents():
            if document.filePath() is not None and \
               document.filePath() == filePath:
                return document

        return None

    def _onAboutToTerminate(self):
        """Enki is going to be terminated.
        Save session
        """
        fileList = [document.filePath() \
                        for document in core.workspace().documents() \
                            if document.filePath() is not None and \
                                os.path.exists(document.filePath()) and \
                                not '/.git/' in document.filePath() and \
                                not (document.fileName().startswith('svn-commit') and \
                                     document.fileName().endswith('.tmp'))]

        if not fileList:
            return

        currentPath = None
        if core.workspace().currentDocument() is not None:
            currentPath = core.workspace().currentDocument().filePath()

        session = {'current' : currentPath,
                   'opened' : fileList}

        enki.core.json_wrapper.dump(_SESSION_FILE_PATH, 'session', session)
