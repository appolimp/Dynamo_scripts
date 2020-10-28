import clr

clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import *

# Import DocumentManager and TransactionManager
clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# Import RevitAPI
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *

# Import ToDSType(bool) extension method
clr.AddReference("RevitNodes")
import Revit

clr.ImportExtensions(Revit.Elements)
# Import ToProtoType, ToRevitType geometry conversion extension methods
clr.ImportExtensions(Revit.GeometryConversion)

# Import DSCore nodes in Dynamo
clr.AddReference('DSCoreNodes')
import DSCore
from DSCore import *

# Import python library
import sys

pyt_path = r'C:\Program Files (x86)\IronPython 2.7\Lib'
sys.path.append(pyt_path)
import os
import shutil
import math
# Import math library
from math import *

# Import Data and Time
from datetime import datetime

now = datetime.now()

# Import System Library
import System
from System.Collections.Generic import *
from System.IO import Directory, Path

doc = DocumentManager.Instance.CurrentDBDocument
uiapp = DocumentManager.Instance.CurrentUIApplication
app = uiapp.Application


def ToList(x):
    if isinstance(x, list):
        return UnwrapElement(x)
    else:
        return [UnwrapElement(x)]


# Preparing input from dynamo to revit
names = ToList(IN[0])
cats = ToList(IN[1])
catids = List[ElementId]()
catids.Clear()
for cc in cats:
    catids.Add(cc.Id)
Parafilele = []

# get parameter id via name
iterator = doc.ParameterBindings.ForwardIterator()
while iterator.MoveNext():
    if iterator.Key.Name == "123":
        pvp = ParameterValueProvider(iterator.Key.Id)
        break

# def subsubset of element filters
ssfilters = List[ElementFilter]()
ssfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringBeginsWith(), "test1", False)))
ssfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringEndsWith(), "test2", False)))
ssfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringLessOrEqual(), "test3", False)))
ssfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringGreaterOrEqual(), "test4", False)))
# define subset of element filters
sfilters = List[ElementFilter]()
sfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringEquals(), "hello1", False)))
sfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringContains(), "hello2", False)))
sfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringContains(), "hello3", False)))
sfilters.Add(ElementParameterFilter(FilterStringRule(pvp, FilterStringContains(), "hello4", False)))
sfilters.Add(LogicalOrFilter(ssfilters))
# define final set of element filters
fRule = LogicalAndFilter(sfilters)

# Do some action in a Transaction
TransactionManager.Instance.EnsureInTransaction(doc)
for name, cat in zip(names, cats):
    paraele = ParameterFilterElement.Create(doc, name, catids)
    paraele.SetElementFilter(fRule)
    Parafilele.append(paraele)
TransactionManager.Instance.TransactionTaskDone()

# Final output
OUT = Parafilele