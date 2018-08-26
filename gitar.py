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

def getChangedFilesFromGit(path_to_repository, branch1, branch2):
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
                lines = subprocess.check_output('git diff --name-only %s...%s' % (branch1, branch2), shell=True).decode(
                    'utf-8').splitlines()
        return [l+"\n" for l in  lines]
    except:
        print("not a git directory")
        return subprocess.check_output("ls", shell=True).decode('utf-8').splitlines()

def getGitToplevelDir():
    try:
        dir = subprocess.check_output('git rev-parse --show-toplevel', shell=True).decode('utf-8').strip()
        return dir+'/'
    except:
        print("not a git directory")
        return ""

def getGitBranches():
    try:
        dir = subprocess.check_output('git branch -a', shell=True).decode('utf-8').strip()
        branches = [b.strip("*").strip() for b in dir.splitlines()]
        return branches
    except:
        print("not a git directory")
        return ""

def getGitCurrentBranch():
    try:
        dir = subprocess.check_output('git symbolic-ref HEAD --short', shell=True).decode('utf-8').strip()
        return dir
    except:
        print("not a git directory")
        return ""


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
                if annotation is not None:
                    self.editor.annotate(idx-1, annotation, 0)
                    annotation=None
                if '\0' in l or '\1' in l:
                    self.editor.append(l.replace('\0+', '').replace('\0-', '').replace('\m', '').replace('\0^', '').replace('\1', ''))
                    self.editor.markerAdd(idx, 0)
                    self.editor.markerAdd(idx, 1)
                    #self.editor.setMarginText(idx, l[1], marginTextStyle)
                    self.editor.fillIndicatorRange(idx, l.find('\0'), idx, l.rfind("\1"), 0)
                else:
                    self.editor.append(l)

class BranchSelector(QWidget):
    def __init__(self, branches=[], callback=None):
        QWidget.__init__(self)
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.branchesMenu = QComboBox()
        self.branchesMenu.addItems(branches)
        self.callback = callback
        self.branchesMenu.currentIndexChanged.connect(self.selectionChange)
        self.layout.addWidget(self.branchesMenu)
        self.layout.setContentsMargins(0,0,0,0)

    def setSelection(self, selection):
        index = self.branchesMenu.findText(selection)
        print(selection)
        if index >= 0:
            self.branchesMenu.setCurrentIndex(index)
        else:
            print("selection not found")

    def selectionChange(self, i):
        if self.callback is not None:
            self.callback()

    def getCurrentBranch(self):
        return self.branchesMenu.currentText()


class CustomMainWindow(QMainWindow):

    def __init__(self):
        super(CustomMainWindow, self).__init__()

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
        self.setGeometry(200, 200, 1200, 800)
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

        self.file_view = QDockWidget()
        #self.file_view_layout = QVBoxLayout()
        #self.file_view.setLayout(self.file_view_layout)
        self.file_view.setWidget(self.file_list)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_view)

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

        self.updateBranches()

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

    ''''''

    def loadFiles(self, args):
        if args is None:
            self.filepath = ""
        else:
            self.filepath = args.text().split(":")[0]
        self.updateDiffView()

    def calcDiffSize(self, filename):
        lines1 = getFromGit(self.gitpath, self.branch1, filename)
        lines2 = getFromGit(self.gitpath, self.branch2, filename)
        left, right, flags = aligner(lines1, lines2)
        return flags.count(True)

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

    def updateBranches(self):

        self.branch1 = str(self.leftBranchSelector.getCurrentBranch())
        self.branch2 = str(self.rightBranchSelector.getCurrentBranch())
        print(self.branch1, self.branch2)
        self.file_list.clear()
        self.files = getChangedFilesFromGit(self.gitpath, self.branch1, self.branch2)
        print(self.files)
        ignore_list=["hex"]
        for f in self.files:
            # if comparing to working copy, only show files that exist locally
            exist=True
            size=0
            if self.branch1=="" or self.branch2=="":
                exist = os.path.isfile(self.gitpath+f.strip())
            if exist and not (f.strip().split(".")[-1]  in ignore_list):
                size=self.calcDiffSize(f)
            if exist and size>0:
                self.file_list.addItem(f.strip()+": (%i)"%size)



    ''''''


''' End Class '''

if __name__ == '__main__':
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create('Fusion'))
    myGUI = CustomMainWindow()

    sys.exit(app.exec_())

''''''
