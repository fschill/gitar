#!/usr/bin/python3
from __future__ import generator_stop
import sys
from PyQt5 import Qt
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.Qsci import *

import difflib
import os, sys, subprocess,  os.path
import re
from collections import defaultdict

import traceback
import time 

import multiprocessing
from multiprocessing import Process, Queue
import functools

def result_as_param(func, queue, *args, **kwargs):
    result = (func(*args, **kwargs))
    queue.put(result)
    print("returned. Result=", len(result))

def timeout(max_timeout):
    """Timeout decorator, parameter in seconds."""
    def timeout_decorator(item):
        """Wrap the original function."""
        @functools.wraps(item)
        def func_wrapper(*args, **kwargs):
            """Closure for function."""
            queue = Queue()
            p = multiprocessing.Process(target=result_as_param, args=[item, queue]+list(args), kwargs=kwargs)
            p.start()

            # Wait for timeout or until process finishes
            p.join(max_timeout)
            result = None
            try:
                result =  queue.get(timeout = max_timeout)
            except:
                print("time out!")
                p.terminate()
            p.join()
            return result
            
            
        return func_wrapper
    return timeout_decorator
    
@timeout(0.5)  
def aligner(lines1, lines2):
    diffs = difflib._mdiff(lines1, lines2)
    fromlist, tolist, flaglist = [], [], []
    # pull from/to data and flags from mdiff style iterator
    itercount = 0
    for fromdata, todata, flag in diffs:
        try:
            # pad lists with "None" at empty lines to align both sides
            if todata[1].startswith('\0+') and fromdata[1].strip()=="":
                fromlist.append(None)  # if todata has an extra line, stuff fromlist with None
            else:
                fromlist.append(fromdata[1]) # otherwise append line
                
            if fromdata[1].startswith('\0-') and todata[1].strip()=="":
                tolist.append(None)    # if fromdata has an extra line, stuff tolist with None
            else:
                tolist.append(todata[1]) # otherwise append line
            
        except TypeError:
            # exceptions occur for lines where context separators go
            fromlist.append(None)
            tolist.append(None)
        flaglist.append(flag)
            
    #for l in fromlist:
    #    print([l])
    print("aligner done")
    return fromlist, tolist, flaglist

class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)

def getFromGit(path_to_repository, branchname, filepath):
    lines=""
    try:
        if branchname == "" or branchname==".":
            #print(path_to_repository+filepath)
            file = open((path_to_repository+filepath).strip())
            #print("file opened")
            lines = file.readlines()
            return [l.rstrip()+"\n" for l in lines]
        else:
            with cd(path_to_repository):
                lines = subprocess.check_output('git show %s:%s'%(branchname, filepath), shell=True).decode('utf-8').splitlines()
            return [l.rstrip()+"\n" for l in  lines]
    except:
        #print("file error")
        return ""

def getChangedFilesFromGit(path_to_repository, branch1, branch2, locallyChangedOnly=False):
    lines=""
    try:
        with cd(path_to_repository):
            if branch1=="" and branch2=="":
                lines = subprocess.check_output('git diff --name-only', shell=True).decode('utf-8').splitlines()
            elif branch1 == "":
                    lines = subprocess.check_output('git diff --name-only %s'%branch2, shell=True).decode('utf-8').splitlines()
            else:
                if branch1==".":
                    branch1  = getGitCurrentBranch()
                if branch2==".":
                    branch2  = getGitCurrentBranch()
                if locallyChangedOnly:
                    lines = subprocess.check_output('git diff --name-only %s...%s' % (branch2, branch1), shell=True).decode(
                    'utf-8').splitlines()
                else:
                    lines = subprocess.check_output('git diff --name-only %s %s' % (branch1, branch2), shell=True).decode(
                        'utf-8').splitlines()
        return [l+"\n" for l in  lines]
    except:
        print("not a git directory")
        return subprocess.check_output("ls", shell=True).decode('utf-8').splitlines()

def getDivergedFiles(path_to_repository, branch1, branch2):
    set1 = getChangedFilesFromGit(path_to_repository, branch1, branch2, True)
    set2 = getChangedFilesFromGit(path_to_repository, branch2, branch1, True)
    combined = [value for value in set1 if value in set2]
    return combined 

def runCommand(commandString):
    try:
        output = subprocess.check_output(commandString, shell=True).decode('utf-8').strip()
        return output
    except:
        print("Error running command:", commandString)
        return ""

def getGitToplevelDir():
    try:
        dir = subprocess.check_output('git rev-parse --show-toplevel', shell=True).decode('utf-8').strip()
        return dir+'/'
    except:
        print("not a git directory")
        return ""

def getGitBranches():
    dir = runCommand('git branch -a')
    branches = [b.strip("*").strip() for b in dir.splitlines()]
    return branches

def getGitCurrentBranch():
    dir = runCommand('git symbolic-ref HEAD --short')
    return dir

def getGitBranchOfCommit(commitHash):
    branch = runCommand('git name-rev %s'%commitHash).split()[1]
    return branch.split('~')[0]

def getGitLog(branch="", file=""):
    output = runCommand('git log --pretty=format:"%H %aI %an: %s" ' + branch + ' -- '+file)
    log = []
    for l in output.splitlines():
        fields = l.split()
        commit = fields[0]
        date = fields[1]
        rest = " ".join(l.split()[2:])
        author = rest.split(":")[0]
        message = ":".join(rest.split(":")[1:])
        log.append((commit, date, author, message))
    return log

def abbreviateString(s, length=40):
    if len(s)>length:
        return s[:length]+".."
    else:
        return s
        
class GitAnnotation:
    line   = 0
    commit = ""
    author = ""
    date   = ""
    time   = ""
    code   = ""

def getGitBlame(branch = "", file=""):
    re_blame = re.compile(r"([0-9a-f]+)[\s]+\(([a-zA-Z\s+]+)\s+(\d+\-\d+-\d+)\s(\d+\:\d+\:\d+)\s([\+\-0-9]+)\s+(\d+)\)(.*)")
    
    
    output = runCommand('git blame -cl ' + branch + ' -- '+file)
    output = output.splitlines()
    
    annotation = []
    for ln, l in enumerate(output):
        parse = re_blame.match(l).groups()
        annot = GitAnnotation()
        annot.line = ln
        annot.commit = parse[0]
        annot.author = parse[1]
        annot.date   = parse[2]
        annot.time   = parse[3]
        annot.code   = parse[6]
        annotation.append(annot)
        
    return annotation

class EditorWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self)
        self.parent=parent
        self.lexers={"cpp":QsciLexerCPP(), "python":QsciLexerPython()}
        self.suffixToLexer={"c":"cpp", "h":"cpp", "cpp":"cpp", "py":"python", "sh":"bash"}
        colormap = ['77AADD', '99DDFF', '44BB99', 'BBCC33', 'AAAA00', 'EEDD88', 'EE8866', 'FFAABB', 'DDDDDD']
        
        self.authorColors = [QsciStyle() for x in colormap]
        for index, x in enumerate(colormap):
            self.authorColors[index].setPaper(QColor("#ff"+x))
            self.authorColors[index].setColor(QColor("#ff000000"))
            
        self.timelineColors = [QsciStyle() for x in range(0, 15)]
        for index, x in enumerate(self.timelineColors):
            r=128
            g=int(255-(index*100/len(self.timelineColors)))
            b=128
            self.timelineColors[index].setPaper(QColor("#88{:02X}{:02X}{:02X}".format(r,g,b)))
            self.timelineColors[index].setColor(QColor("#88000000"))
            
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.toolbar=QWidget()
        self.toolbarLayout = QHBoxLayout()
        self.toolbar.setLayout(self.toolbarLayout)
        self.label = QLabel()
        self.editor = QsciScintilla()
        
        self.configureEditor(self.editor)
        
        self.filename=None
        self.rawText=None
        self.saveButton = QPushButton("save")
        self.saveButton.setFixedWidth(80)
        self.saveButton.setDisabled(True)
        self.saveButton.clicked.connect(self.saveText)

        self.annotateCheckbox = QCheckBox("annotation")
        self.annotateCheckbox.stateChanged.connect(self.refreshText)

        self.toolbarLayout.addWidget(self.saveButton)
        self.toolbarLayout.addWidget(self.label)
        self.toolbarLayout.addWidget(self.annotateCheckbox)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.editor)

        self.toolbarLayout.setContentsMargins(0, 0, 0, 0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.marginTextStyle= QsciStyle()
        self.marginTextStyle.setPaper(QColor("#ffFF8888"))

        

        if parent is not None: # connect to update for text change
            self.editor.textChanged.connect(self.parent.updateAfterEdit)


    def configureEditor(self, editor):
        self.__lexer = self.lexers["cpp"]
        editor.setLexer(self.__lexer)
        #editor.setMarginType(1, QsciScintilla.TextMargin)
        editor.setMarginType(1, QsciScintilla.SymbolMargin)
        editor.setMarginType(2, QsciScintilla.TextMargin) #margin for author/blame info
        editor.setMarginType(3, QsciScintilla.SymbolMargin) #margin for timeline coloring
        
        editor.setMarginSensitivity(3, True) # make time line margin clickable
        editor.marginClicked.connect(self.timelineLeftClick)
        editor.marginRightClicked.connect(self.timelineRightClick)
        
        editor.setMarginMarkerMask(1, 0b11)
        editor.setMarginMarkerMask(0, 0b11)
        editor.setMarginMarkerMask(3, 0b11111111111111100)
        editor.setMarginsForegroundColor(QColor("#ffFF8888"))
        editor.markerDefine(QsciScintilla.Background, 0)
        editor.setMarkerBackgroundColor(QColor("#22FF8888"),0)
        editor.setMarkerForegroundColor(QColor("#ffFF8888"),0)
        editor.markerDefine(QsciScintilla.Rectangle, 1)
        editor.setMarkerBackgroundColor(QColor("#ffFF8888"),1)
        editor.setMarkerForegroundColor(QColor("#ffFF8888"),1)
        
        for idx, col in enumerate(self.timelineColors):
            editor.markerDefine(QsciScintilla.Rectangle, idx+3)
            editor.setMarkerBackgroundColor(col.paper(),idx+3)
            editor.setMarkerForegroundColor(col.color(),idx+3)
            
        editor.setUtf8(True)  # Set encoding to UTF-8
        #editor.indicatorDefine(QsciScintilla.FullBoxIndicator, 0)
        #editor.indicatorDefine(QsciScintilla.BoxIndicator, 0)
        editor.indicatorDefine(QsciScintilla.StraightBoxIndicator, 0)
        editor.setIndicatorForegroundColor(QColor("#44FF8888"),0)
        editor.setAnnotationDisplay(QsciScintilla.AnnotationStandard)

    def timelineLeftClick(self, margin_nr, line_nr, state):
        if self.blame is not None:
            ln = self.blame[line_nr]
            print(line_nr, ln.commit, ln.date, ln.time, ln.author)
            branchName = getGitBranchOfCommit(ln.commit)
            print("commit is on branch", branchName)
            self.parent.branch2 = ln.commit
            self.parent.rightBranchSelector.setSelection(branchName)
            self.parent.rightBranchSelector.setCommit(ln.commit)
            self.parent.updateDiffView()

    def timelineRightClick(self, margin_nr, line_nr, state):
        print("Margin clicked (right mouse btn)!")
        print(" -> margin_nr: " + str(margin_nr))
        print(" -> line_nr:   " + str(line_nr))
        print("")


    def refreshText(self):
        self.updateText(self.rawText, self.branch, self.filename)

    def updateText(self, text, branch, filename, fileSuffix="c"):
        self.editor.blockSignals(True) # turn off signals to avoid update loops
        self.branch = branch
        self.rawText = text

        self.blame = None
        self.editor.setMarginWidth(2, 0) # hide blame margin by default
        self.editor.setMarginWidth(3, 0)
        authors = defaultdict(lambda: 0)
        times = defaultdict(lambda: 0)
        
        if self.annotateCheckbox.isChecked():
            self.blame = getGitBlame(self.branch, filename)
            for ln in self.blame:
                authors[ln.author] = authors[ln.author]+1  #count contributions, and sort top-down
                times[ln.date] = 0
                
            sort_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)
            sort_times = sorted(times.items(), key=lambda x: x[0], reverse=True)
            #rebuild author dict with descending ID by contributions
            for index, rec in enumerate(sort_authors):
                authors[rec[0]] = [index, rec[1]]
            # index all commit times new to old
            for index, rec in enumerate(sort_times):
                times[rec[0]] = index
            #print(times.items())
            #print(authors.items())
            self.editor.setMarginWidth(2, "0000") # show blame margin
            self.editor.setMarginWidth(3, "0000") # show timeline margin
        
        if self.branch == "":
            self.saveButton.setText("save")
            self.saveButton.setDisabled(False)

        else:
            self.saveButton.setText("checkout")
            self.saveButton.setDisabled(False)

        firstLine = 0
        cursorLine = 0
        cursorIndex = 0
        if self.filename == filename: # if it's still the same file, keep scroll and cursor position
            firstLine = self.editor.firstVisibleLine()
            cursorLine, cursorIndex = self.editor.getCursorPosition()
        self.filename = filename # store filename
        label = branch+":"+filename
        if fileSuffix in self.suffixToLexer.keys():
            self.__lexer = self.lexers[self.suffixToLexer[fileSuffix]]
            self.editor.setLexer(self.__lexer)
            #label+="     ("+self.suffixToLexer[fileSuffix]+")"
        
        
        
        self.editor.setMarginsBackgroundColor(QColor("#ff888888"))
        self.editor.clearAnnotations(-1)
        self.editor.setText("")
        self.label.setText(label)
        skipped_lines = 0
        annotation=None

        for linenumber, l in enumerate(text):
            idx=linenumber-skipped_lines
            if l is None:
                #editor.append("\n")
                if annotation is None:
                    annotation="<"
                else:
                    annotation+="\n<"
                skipped_lines+=1
                #self.editor.setMarginText(idx, "~", marginTextStyle)
                self.editor.markerAdd(idx, 1)
            else:

                if '\0' in l or '\1' in l:
                    self.editor.append(l.replace('\0+', '').replace('\0-', '').replace('\m', '').replace('\0^', '').replace('\1', ''))
                    self.editor.markerAdd(idx, 0)
                    self.editor.markerAdd(idx, 1)
                    #self.editor.setMarginText(idx, l[1], marginTextStyle)
                    ind_left = l.find('\0')
                    ind_right = l.rfind("\1")
                    #print(ind_left, ind_right, len(l))
                    self.editor.fillIndicatorRange(idx, ind_left, idx, ind_right, 0)
                else:
                    self.editor.append(l)
                    
                bltag = ""
                if self.blame is not None:
                    author_idx= min(authors[self.blame[idx].author][0], len(self.authorColors)-1) # get color index 
                    time_idx = min(times[self.blame[idx].date], len(self.timelineColors)-2)
                    bltag = "".join([a[0] for a in self.blame[idx].author.split()])
                    self.editor.setMarginText(idx, bltag, self.authorColors[author_idx])
                    #self.editor.setMarginText(idx, bltag, self.timelineColors[time_idx])
                    self.editor.markerAdd(idx, time_idx+3)
                    #self.editor.fillIndicatorRange(idx, ind_left, idx, ind_right, 0)
                    
                if annotation is not None:
                    if (idx>0):
                        self.editor.annotate(idx-1, annotation, 0)
                    else:
                        #self.editor.append("\n")
                        self.editor.annotate(idx, annotation, 0)
                    annotation=None
        self.editor.setFirstVisibleLine(firstLine)
        self.editor.setCursorPosition(cursorLine, cursorIndex)
        self.editor.blockSignals(False) # turn signals on again

    def getText(self):
        return self.editor.text().splitlines(True)

    def saveText(self):
        if self.branch == "":
            f=open(self.filename, "w")
            f.write(self.editor.text())
            print("saved ", self.filename)
            self.parent.updateDiffView()


class BranchSelector(QWidget):
    def __init__(self, branches=[], callback=None):
        QWidget.__init__(self)
        self.layout = QVBoxLayout()
        self.menuWidget = QWidget()
        self.menulayout = QHBoxLayout()
        self.setLayout(self.layout)
        self.menuWidget.setLayout(self.menulayout)
        self.branchesMenu = QComboBox()
        self.branchesMenu.addItems(branches)
        self.callback = callback
        self.branchesMenu.currentIndexChanged.connect(self.selectionChange)
        self.commitMenu = QComboBox()
        self.commitMenu.currentIndexChanged.connect(self.commitChange)
        self.commitMenu.setMaxVisibleItems(15)
        self.commitSlider = QSlider(Qt.Horizontal)
        self.commitSlider.setTickInterval(1)
        self.commitSlider.setTickPosition(QSlider.TicksBothSides)
        self.menulayout.addWidget(self.branchesMenu)
        self.menulayout.addWidget(self.commitMenu)
        self.layout.addWidget(self.menuWidget)
        #self.layout.addWidget(self.commitSlider)
        self.menulayout.setContentsMargins(0,0,0,0)
        self.layout.setContentsMargins(0,0,0,0)
        self.gitlog = None

    def setSelection(self, selection):
        index = self.branchesMenu.findText(selection)
        print("found selection", selection)
        if index >= 0 and index!=self.commitMenu.currentIndex():
            self.branchesMenu.setCurrentIndex(index)
        else:
            print("selection not found")

    def setCommit(self, commit):
        index = [x[0] for x in self.gitlog].index(commit)
        if index >= 0:
            self.commitMenu.setCurrentIndex(index)
            print("jumping to commit ", self.gitlog[index])
        else:
            print("commit not found", commit)

    def updateCommitMenu(self):
        selectedBranch = self.branchesMenu.currentText()
        if selectedBranch ==".":
            selectedBranch = getGitCurrentBranch()
        if selectedBranch == "":
            self.gitlog = None
        else:
            self.gitlog = getGitLog(branch=selectedBranch)
        print ("updating commit list...")
        self.commitMenu.blockSignals(True)
        self.commitMenu.clear()
        if self.gitlog is None or len(self.gitlog) == 0:
            return
        print(self.gitlog[0])
        self.commitMenu.addItems([abbreviateString(log[2]+": "+log[3], length=50) for log in self.gitlog])
        for i in range(0, len(self.gitlog)):
            self.commitMenu.setItemData(i, self.gitlog[i][1]+" - "+self.gitlog[i][2]+": "+self.gitlog[i][3], Qt.ToolTipRole)

        self.commitMenu.blockSignals(False)
        self.commitSlider.setMinimum(0)
        self.commitSlider.setMaximum(len(self.gitlog))

    def selectionChange(self, i):
        self.updateCommitMenu()
        if self.callback is not None:
            self.callback()

    def commitChange(self, i):
        if self.callback is not None:
            self.callback()

    def getCurrentBranch(self):
        #return self.branchesMenu.currentText()
        if self.gitlog is not None:
            return self.gitlog[self.commitMenu.currentIndex()][0]
        else:
            return self.branchesMenu.currentText()


class FileListUpdateThread(QThread):
    entryChanged = pyqtSignal(int, int)

    def __init__(self, mainWindow):
        QThread.__init__(self)
        self.mainWindow = mainWindow
        self.restart=False
        self.stop = False

    def run(self):
        print("thread start")
        self.restart=True
        #while self.restart:
        self.restart=False
        for i in range(0, self.mainWindow.file_list.count()):
            try:
                f = self.mainWindow.file_list.item(i).text().split(":")[0]
            except:
                restart=True
                break
            print ("processing", f)
            try:
                size = self.mainWindow.calcDiffSize(f)
                print (f, size)
                self.entryChanged.emit(i, size)
            except:
                print("error calculating diff size")
            #check if we need to restart
            if self.restart:
                break
    
        print("thread end")


class CustomMainWindow(QMainWindow):

    def __init__(self):
        super(CustomMainWindow, self).__init__()

        self.updateThread = FileListUpdateThread(self)

        # Window setup
        # --------------

        self.gitpath = getGitToplevelDir()
        print(self.gitpath)
        self.filepath = ""
        self.branch1 = ""
        self.branch2 = getGitCurrentBranch()

        branches = getGitBranches()

        if len(sys.argv)==2:
            self.branch2 = sys.argv[1]

        if len(sys.argv)==3:
            self.branch1 = sys.argv[1]
            self.branch2 = sys.argv[2]


        # 1. Define the geometry of the main window
        self.setGeometry(200, 100, 1900, 900)
        self.setWindowTitle("Gitar")

        # 2. Create frame and layout
        self.__frm = QFrame(self)
        self.__frm.setStyleSheet("QWidget { background-color: #ffeaeaea }")
        self.__lyt = QVBoxLayout()
        self.__frm.setLayout(self.__lyt)
        self.setCentralWidget(self.__frm)
        self.__myFont = QFont()
        self.__myFont.setPointSize(14)

        # File list widget
        self.file_list=QListWidget()
        self.file_list.currentItemChanged.connect(self.loadFiles)
        self.file_list.clicked.connect(self.updateDiffView)
        self.updateThread.entryChanged.connect(self.updateDiffSize)

        self.localChangesCheckbox = QCheckBox("Local changes only")
        self.divergedCheckbox = QCheckBox("diverged files only")

        self.file_view = QWidget()
        self.file_view_layout = QVBoxLayout()
        self.file_view.setLayout(self.file_view_layout)
        self.file_view_layout.addWidget(self.localChangesCheckbox)
        self.file_view_layout.addWidget(self.divergedCheckbox)
        self.file_view_layout.addWidget(self.file_list)

        self.file_view_dock = QDockWidget()
        self.file_view_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        self.file_view_dock.setWidget(self.file_view)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_view_dock)

        #create side-by-side view with vertical splitter

        self.comparison_area = QSplitter(Qt.Horizontal)

        # QScintilla editor setup
        # ------------------------

        # ! Make instance of QsciScintilla class!
        self.left_editor = EditorWidget(parent=self)

        self.right_editor = EditorWidget(parent=self)

        self.comparison_area.addWidget(self.left_editor)
        self.comparison_area.addWidget(self.right_editor)


        self.branchesMenu = QWidget()
        self.branchesMenuLayout = QHBoxLayout()
        self.branchesMenu.setLayout(self.branchesMenuLayout)
        self.branchesMenu.setFixedHeight(50)
        self.branchesMenuLayout.setContentsMargins(0,0,0,0)


        self.leftBranchSelector = BranchSelector(branches = ["", "."]+branches, callback = self.updateBranches)
        self.rightBranchSelector = BranchSelector(branches = branches, callback = self.updateBranches)

        self.leftBranchSelector.setSelection(self.branch1)
        self.rightBranchSelector.setSelection(self.branch2)

        self.branchesMenuLayout.addWidget(self.leftBranchSelector)
        self.branchesMenuLayout.addWidget(self.rightBranchSelector)

        # ! Add editor to layout !
        self.__lyt.addWidget(self.branchesMenu)
        self.__lyt.addWidget(self.comparison_area)

        self.show()

        self.left_editor.editor.verticalScrollBar().valueChanged.connect( self.right_editor.editor.verticalScrollBar().setValue)
        self.localChangesCheckbox.stateChanged.connect(self.updateBranches)
        self.divergedCheckbox.stateChanged.connect(self.updateBranches)
        self.updateBranches()

    ''''''

    def loadFiles(self, args):
        print("loading files")
        if args is None:
            #self.filepath = ""
            pass
        else:
            self.filepath = args.text().split(":")[0]
        self.updateDiffView()

    def calcDiffSize(self, filename):
        lines1 = getFromGit(self.gitpath, self.branch1, filename)
        lines2 = getFromGit(self.gitpath, self.branch2, filename)
        try:
            left, right, flags = aligner(lines1, lines2)
            return flags.count(True)
        except TypeError:
            print("Aligner timed out")
            return 0

    def updateDiffSize(self, i, size):
        item = self.file_list.item(i)
        if item is not None:
            item.setText(self.files[i].strip()+": (%i)"%size)

    def updateDiffView(self):
        print("update diff")
        lines1=[""]
        lines2=[""]
        editorPosition = self.left_editor.editor.verticalScrollBar().value()
        
        if self.filepath is None or self.filepath =="":
            lines1 = []
            lines2 = []
        else:
            lines1 = getFromGit(self.gitpath, self.branch1, self.filepath)
            lines2 = getFromGit(self.gitpath, self.branch2, self.filepath)
        
        try:
            left, right, flags = aligner(lines1, lines2)
            self.left_editor.updateText( left,  self.branch1, self.filepath, fileSuffix=self.filepath.split(".")[-1])
            self.right_editor.updateText(right, self.branch2, self.filepath, fileSuffix=self.filepath.split(".")[-1])
        except TypeError:
            print("Aligner timed out")
        self.left_editor.editor.verticalScrollBar().setValue(editorPosition)

    def updateAfterEdit(self):
        lines1 = self.left_editor.getText()
        lines2 = self.right_editor.getText()
        left, right, flags = aligner(lines1, lines2)
        self.left_editor.updateText( left,  self.branch1, self.filepath, fileSuffix=self.filepath.split(".")[-1])
        self.right_editor.updateText(right, self.branch2, self.filepath, fileSuffix=self.filepath.split(".")[-1])

    def updateBranches(self, *args):
        
        # store editor file position
        editorPosition = self.left_editor.editor.verticalScrollBar().value()

        self.branch1 = str(self.leftBranchSelector.getCurrentBranch())
        self.branch2 = str(self.rightBranchSelector.getCurrentBranch())
        print(self.branch1, self.branch2)
        self.file_list.clear()
        if self.divergedCheckbox.isChecked():
            self.files = getDivergedFiles(self.gitpath, self.branch1, self.branch2)
        else:
            self.files = getChangedFilesFromGit(self.gitpath, self.branch1, self.branch2, locallyChangedOnly=self.localChangesCheckbox.isChecked())
        
        print("collecting files")
        #print(self.files)
        ignore_list=["hex"]
        for f in self.files:
            # if comparing to working copy, only show files that exist locally
            exist=True
            size=0
            if self.branch1=="" or self.branch2=="":
                exist = os.path.isfile(self.gitpath+f.strip())

            #if exist and not (f.strip().split(".")[-1]  in ignore_list):
            #    size=self.calcDiffSize(f)
            if exist:
                self.file_list.addItem(f.strip()+": (...)")

        # check if previously selected file is still there
        filenames = [fn.split(":")[0].strip() for fn in self.files]
        if self.filepath in filenames:
            print("reselect file " + self.filepath)
            findex = filenames.index(self.filepath)
            
            oldState = self.file_list.blockSignals(True)
            self.file_list.setCurrentRow(findex)
            self.file_list.blockSignals(oldState)
            self.updateDiffView()
            # reset editor scroll position
            self.left_editor.editor.verticalScrollBar().setValue(editorPosition)
        else: 
            print("cannot reselect file: not found.", self.filepath)
        self.updateThread.restart=True
        self.updateThread.start()

    ''''''


''' End Class '''

if __name__ == '__main__':
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create('Fusion'))
    myGUI = CustomMainWindow()

    sys.exit(app.exec_())

''''''
