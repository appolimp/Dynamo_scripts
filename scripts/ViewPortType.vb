Imports Autodesk.Revit.UI
Imports Autodesk.Revit.DB

'How to use this
'Set a sheet view active with 2 viewports on (Could be 2 floor plans on a sheet.)
'Select both viewports (the last selected viewport will be changed to same type of viewport as the first selected viewport.)
<Autodesk.Revit.Attributes.Transaction(Autodesk.Revit.Attributes.TransactionMode.Manual)> _
<Autodesk.Revit.Attributes.Regeneration(Autodesk.Revit.Attributes.RegenerationOption.Manual)> _
Public Class ViewPortType
    Implements IExternalCommand

    Public Function Execute(commandData As Autodesk.Revit.UI.ExternalCommandData, ByRef message As String, elements As Autodesk.Revit.DB.ElementSet) As Autodesk.Revit.UI.Result Implements Autodesk.Revit.UI.IExternalCommand.Execute
        Dim transaction As Transaction = New Transaction(commandData.Application.ActiveUIDocument.Document, "LoadFamily")
        Dim viewPortTemplate As Viewport = Nothing
        Dim viewPortNew As Viewport = Nothing
        Try
            transaction.Start()

            viewPortTemplate = commandData.Application.ActiveUIDocument.Selection.Elements(0)
            viewPortNew = commandData.Application.ActiveUIDocument.Selection.Elements(1)

            viewPortNew.Parameter(BuiltInParameter.ELEM_FAMILY_AND_TYPE_PARAM).Set(viewPortTemplate.Parameter(BuiltInParameter.ELEM_FAMILY_AND_TYPE_PARAM).AsElementId)

            transaction.Commit()
            Return Result.Succeeded
        Catch ex As Exception
            transaction.RollBack()
            Return Result.Failed
        End Try
    End Function

End Class
