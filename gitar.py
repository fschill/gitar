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
            # store HTML markup of the lines into the lists
            if todata[1].startswith('\0+') and fromdata[1].strip()=="":
                fromlist.append(None)
            else:
                fromlist.append(fromdata[1])
            if fromdata[1].startswith('\0-') and todata[1].strip()=="":
                tolist.append(None)
            else:
                tolist.append(todata[1])
        except TypeError:
            # exceptions occur for lines where context separators go
            fromlist.append(None)
            tolist.append(None)
        flaglist.append(flag)
    #for l in fromlist:
    #    print([l])
    return fromlist, tolist, flaglist
    #return fromlist, lines2, flaglist

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
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.label = QLabel()
        self.editor = QsciScintilla()
        self.configureEditor(self.editor)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.editor)
        
    def configureEditor(self, editor):
        self.__lexer = QsciLexerCPP()
        editor.setLexer(self.__lexer)
        editor.setMarginType(1, QsciScintilla.TextMargin)
        editor.setMarginType(0, QsciScintilla.SymbolMargin)
        editor.setMarginMarkerMask(1, 0b1111)
        editor.setMarginMarkerMask(0, 0b1111)
        editor.setMarginsForegroundColor(QColor("#ffFF8888"))
        editor.setUtf8(True)  # Set encoding to UTF-8
        #editor.indicatorDefine(QsciScintilla.FullBoxIndicator, 0)
        editor.indicatorDefine(QsciScintilla.BoxIndicator, 0)
        editor.setAnnotationDisplay(QsciScintilla.AnnotationStandard)

    def updateText(self, text,  label=""):
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
                self.editor.setMarginText(idx, "~", marginTextStyle)
            else:
                if annotation is not None:
                    self.editor.annotate(idx-1, annotation, 0)
                    annotation=None
                if '\0' in l or '\1' in l:
                    self.editor.append(l.replace('\0+', '').replace('\0-', '').replace('\m', '').replace('\0^', '').replace('\1', ''))
                    self.editor.markerAdd(idx, QsciScintilla.Circle)
                    self.editor.setMarginText(idx, l[1], marginTextStyle)
                    self.editor.fillIndicatorRange(idx, l.find('\0'), idx, l.rfind("\1"), 0)
                else:
                    self.editor.append(l)

        
class CustomMainWindow(QMainWindow):

    def __init__(self):
        super(CustomMainWindow, self).__init__()

        # Window setup
        # --------------

        #self.gitpath = "/home/felix/Hydromea/AUV_Software/Bootloader/Library/"
        self.gitpath = getGitToplevelDir()
        print(self.gitpath)
        self.filepath = "communication/mavboot.c"
        self.branch1 = ""
        self.branch2 = getGitCurrentBranch()

        if len(sys.argv)==2:
            self.branch2 = sys.argv[1]

        if len(sys.argv)==3:
            self.branch1 = sys.argv[1]
            self.branch2 = sys.argv[2]

        #self.branch2 = ""
        #testfile1 = open("test1.c")
        #lines1=testfile1.readlines()
        #testfile2 = open("test2.c")
        #lines2=testfile2.readlines()


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

        #create side-by-side view with vertical splitter

        self.comparison_area = QSplitter(Qt.Horizontal)

        # File list widget
        self.file_list=QListWidget()
        self.files = getChangedFilesFromGit(self.gitpath, self.branch1, self.branch2)
        self.file_list.currentItemChanged.connect(self.loadFiles)

        self.file_view = QDockWidget()
        #self.file_view_layout = QVBoxLayout()
        #self.file_view.setLayout(self.file_view_layout)
        self.file_view.setWidget(self.file_list)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_view)

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

        # QScintilla editor setup
        # ------------------------

        # ! Make instance of QsciScintilla class!
        self.left_editor = EditorWidget()

        self.right_editor = EditorWidget()

        self.comparison_area.addWidget(self.left_editor)
        self.comparison_area.addWidget(self.right_editor)

        # ! Add editor to layout !
        self.__lyt.addWidget(self.comparison_area)

        self.show()

        self.left_editor.editor.verticalScrollBar().valueChanged.connect( self.right_editor.editor.verticalScrollBar().setValue)

    ''''''

    def loadFiles(self, args):
        self.filepath = args.text().split(":")[0]
        self.updateDiffView()

    def calcDiffSize(self, filename):
        lines1 = getFromGit(self.gitpath, self.branch1, filename)
        lines2 = getFromGit(self.gitpath, self.branch2, filename)
        left, right, flags = aligner(lines1, lines2)
        return flags.count(True)

    def updateDiffView(self):
        lines1 = getFromGit(self.gitpath, self.branch1, self.filepath)
        lines2 = getFromGit(self.gitpath, self.branch2, self.filepath)

        left, right, flags = aligner(lines1, lines2)
        self.left_editor.updateText( left,  self.branch1+" : "+self.filepath)
        self.right_editor.updateText(right, self.branch2+" : "+self.filepath)


    def __btn_action(self):
        self.right_editor.setFirstVisibleLine(self.left_editor.firstVisibleLine())

    ''''''


''' End Class '''

if __name__ == '__main__':
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create('Fusion'))
    myGUI = CustomMainWindow()

    sys.exit(app.exec_())

''''''
