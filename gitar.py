#!/usr/bin/python3
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.Qsci import *

import difflib
import os, sys, subprocess,  os.path

def aligner(lines1, lines2):
    diffs = difflib._mdiff(lines1, lines2)
    fromlist, tolist, flaglist = [], [], []
    # pull from/to data and flags from mdiff style iterator
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

class EditorWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.lexers={"cpp":QsciLexerCPP(), "python":QsciLexerPython()}
        self.suffixToLexer={"c":"cpp", "h":"cpp", "cpp":"cpp", "py":"python", "sh":"bash"}

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.label = QLabel()
        self.editor = QsciScintilla()
        self.configureEditor(self.editor)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.editor)


    def configureEditor(self, editor):
        self.__lexer = self.lexers["cpp"]
        editor.setLexer(self.__lexer)
        #editor.setMarginType(1, QsciScintilla.TextMargin)
        editor.setMarginType(1, QsciScintilla.SymbolMargin)
        editor.setMarginMarkerMask(1, 0b1111)
        editor.setMarginMarkerMask(0, 0b1111)
        editor.setMarginsForegroundColor(QColor("#ffFF8888"))
        editor.markerDefine(QsciScintilla.Background, 0)
        editor.setMarkerBackgroundColor(QColor("#22FF8888"),0)
        editor.setMarkerForegroundColor(QColor("#ffFF8888"),0)
        editor.markerDefine(QsciScintilla.Rectangle, 1)
        editor.setMarkerBackgroundColor(QColor("#ffFF8888"),1)
        editor.setMarkerForegroundColor(QColor("#ffFF8888"),1)
        editor.setUtf8(True)  # Set encoding to UTF-8
        #editor.indicatorDefine(QsciScintilla.FullBoxIndicator, 0)
        #editor.indicatorDefine(QsciScintilla.BoxIndicator, 0)
        editor.indicatorDefine(QsciScintilla.StraightBoxIndicator, 0)
        editor.setIndicatorForegroundColor(QColor("#44FF8888"),0)
        editor.setAnnotationDisplay(QsciScintilla.AnnotationStandard)

    def updateText(self, text,  label="", fileSuffix="c"):

        if fileSuffix in self.suffixToLexer.keys():
            self.__lexer = self.lexers[self.suffixToLexer[fileSuffix]]
            self.editor.setLexer(self.__lexer)
            #label+="     ("+self.suffixToLexer[fileSuffix]+")"
        marginTextStyle= QsciStyle()
        marginTextStyle.setPaper(QColor("#ffFF8888"))
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

                if annotation is not None:
                    if (idx>0):
                        self.editor.annotate(idx-1, annotation, 0)
                    else:
                        #self.editor.append("\n")
                        self.editor.annotate(idx, annotation, 0)
                    annotation=None

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
        print(selection)
        if index >= 0:
            self.branchesMenu.setCurrentIndex(index)
        else:
            print("selection not found")

    def selectionChange(self, i):
        selectedBranch = self.branchesMenu.currentText()
        if selectedBranch ==".":
            selectedBranch = getGitCurrentBranch()
        if selectedBranch == "":
            self.gitlog = None
        else:
            self.gitlog = getGitLog(branch=selectedBranch)
        self.commitMenu.clear()
        if len(self.gitlog) == 0:
            return
        print(self.gitlog[0])
        self.commitMenu.addItems([abbreviateString(log[2]+": "+log[3], length=50) for log in self.gitlog])
        for i in range(0, len(self.gitlog)):
            self.commitMenu.setItemData(i, self.gitlog[i][1]+" - "+self.gitlog[i][2]+": "+self.gitlog[i][3], Qt.ToolTipRole)

        self.commitSlider.setMinimum(0)
        self.commitSlider.setMaximum(len(self.gitlog))
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

    def run(self):
        #print("thread start")
        self.restart=True
        while self.restart:
            self.restart = False
            for i in range(0, self.mainWindow.file_list.count()):
                try:
                    file = self.mainWindow.file_list.item(i).text().split(":")[0]
                except:
                    restart=True
                    break
                size = self.mainWindow.calcDiffSize(file)
                print (file, size)
                self.entryChanged.emit(i, size)
                #check if we need to restart
                if self.restart:
                    break
        #print("thread end")


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
        self.setGeometry(200, 100, 1600, 800)
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
        self.updateThread.entryChanged.connect(self.updateDiffSize)

        self.localChangesCheckbox = QCheckBox("Local changes only")

        self.file_view = QWidget()
        self.file_view_layout = QVBoxLayout()
        self.file_view.setLayout(self.file_view_layout)
        self.file_view_layout.addWidget(self.localChangesCheckbox)
        self.file_view_layout.addWidget(self.file_list)

        self.file_view_dock = QDockWidget()
        self.file_view_dock.setWidget(self.file_view)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_view_dock)

        #create side-by-side view with vertical splitter

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

        self.comparison_area = QSplitter(Qt.Horizontal)

        # QScintilla editor setup
        # ------------------------

        # ! Make instance of QsciScintilla class!
        self.left_editor = EditorWidget()

        self.right_editor = EditorWidget()

        self.comparison_area.addWidget(self.left_editor)
        self.comparison_area.addWidget(self.right_editor)

        # ! Add editor to layout !
        self.__lyt.addWidget(self.branchesMenu)
        self.__lyt.addWidget(self.comparison_area)

        self.show()

        self.left_editor.editor.verticalScrollBar().valueChanged.connect( self.right_editor.editor.verticalScrollBar().setValue)
        self.localChangesCheckbox.stateChanged.connect(self.updateBranches)

        self.updateBranches()

    ''''''

    def loadFiles(self, args):
        if args is None:
            #self.filepath = ""
            pass
        else:
            self.filepath = args.text().split(":")[0]
        self.updateDiffView()

    def calcDiffSize(self, filename):
        lines1 = getFromGit(self.gitpath, self.branch1, filename)
        lines2 = getFromGit(self.gitpath, self.branch2, filename)
        left, right, flags = aligner(lines1, lines2)
        return flags.count(True)

    def updateDiffSize(self, i, size):
        item = self.file_list.item(i)
        if item is not None:
            item.setText(self.files[i].strip()+": (%i)"%size)

    def updateDiffView(self):
        lines1=[""]
        lines2=[""]
        if self.filepath is None or self.filepath =="":
            lines1 = []
            lines2 = []
        else:
            lines1 = getFromGit(self.gitpath, self.branch1, self.filepath)
            lines2 = getFromGit(self.gitpath, self.branch2, self.filepath)

        left, right, flags = aligner(lines1, lines2)
        self.left_editor.updateText( left,  self.branch1+" : "+self.filepath, fileSuffix=self.filepath.split(".")[-1])
        self.right_editor.updateText(right, self.branch2+" : "+self.filepath, fileSuffix=self.filepath.split(".")[-1])

    def updateBranches(self, *args):
        # store editor file position
        editorPosition = self.left_editor.editor.verticalScrollBar().value()

        self.branch1 = str(self.leftBranchSelector.getCurrentBranch())
        self.branch2 = str(self.rightBranchSelector.getCurrentBranch())
        print(self.branch1, self.branch2)
        self.file_list.clear()
        self.files = getChangedFilesFromGit(self.gitpath, self.branch1, self.branch2, locallyChangedOnly=self.localChangesCheckbox.isChecked())
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
            self.file_list.setCurrentRow(findex)
            self.updateDiffView()
            # reset editor scroll position
            self.left_editor.editor.verticalScrollBar().setValue(editorPosition)
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
