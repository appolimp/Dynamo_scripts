from base.selection import get_selected
from base.wrapper import doc, uidoc, UI


def get_preselected_elems_or_invite():
    """
    Get list pre-selected elements or invite user to select

    :return: List of selected elements
    :rtype: list
    """

    selected = get_selected(as_list=True)
    if selected:
        return selected

    ref_elem = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element)
    elem = doc.GetElement(ref_elem.ElementId)
    return [elem]
