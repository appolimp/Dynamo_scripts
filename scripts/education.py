# coding=utf-8
import clr

clr.AddReference('RevitAPI')
clr.AddReference("RevitServices")
import Autodesk.Revit.DB as DB
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument


def main():

    all_room = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms)  # Find all room in Revit

    room_dest = {}
    for room in all_room:
        area = room.get_Parameter(DB.BuiltInParameter.ROOM_AREA).AsDouble()  # Get area for ignore deleted rooms
        destination = room.get_Parameter(DB.BuiltInParameter.ROOM_DEPARTMENT).AsString()  # Get "Назначение"

        if area > 0.0 and destination:  # Если у помещение размещено в проекте и у него заполнен параметр назначение
            room_dest.setdefault(destination, []).append(room)

    return room_dest


if __name__ == '<module>' or __name__ == '__main__':
    try:
        OUT = main()
    except Exception as err:
        raise
