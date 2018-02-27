# gitar
Graphical git diff tool to compare branches

*** work in progress ***
Gitar is a tool that provides a side-by-side diff across different branches of a repository. Branches can be compared directly without checkout, gitar will obtain the file contents directly from git without modifying the working copy.

Installation:
~~~~~~~~~~~~~

Copy or link gitar.py into a folder within the path, and give it execution permission (chmod u+x gitar.py).

Usage:
~~~~~~

path/of/git/repo> gitar.py [branch1] [branch2]

If no branches are given, the state of the working copy is compared to the HEAD of the currently active branch.
If one branch is given, the working copy is compared to the specified branch.
If two branches are given, all files are shown that were changed in branch2 since it forked

The main window provides a file list of changed files, and a side-by-side view of the selected file in branch1 vs. branch2.
