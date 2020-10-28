#Boilerplate Code

task_dialog = TaskDialog("Example Title")
task_dialog.CommonButtons = TaskDialogCommonButtons.Cancel | TaskDialogCommonButtons.Ok | TaskDialogCommonButtons.Close |     TaskDialogCommonButtons.No | TaskDialogCommonButtons.Yes | TaskDialogCommonButtons.Retry | TaskDialogCommonButtons.None
task_dialog.FooterText = "Example Footer Text"
task_dialog.MainInstruction = "Example Main Instruction"
task_dialog.MainContent = "This is the main content for this TaskDialog"

task_dialog.Show()