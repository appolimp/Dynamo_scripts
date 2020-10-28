# Copyright(c) 2018, Petar Penchev
# @All 1 Studio, http://all1studio.com

import clr

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *
import Autodesk

clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument

definition = []
paramElement = []
sharedParams = []
sharedParamNames = []

bindingsMap = doc.ParameterBindings
iterator = bindingsMap.ForwardIterator()

while iterator.MoveNext():
    definition.append(iterator.Key)
    paramElement.append(doc.GetElement(iterator.Key.Id))

for d, pe in zip(definition, paramElement):
    if pe.ToString() == "Autodesk.Revit.DB.SharedParameterElement":
        sharedParams.append(d)
        sharedParamNames.append(d.Name)

OUT = sharedParams, sharedParamNames

